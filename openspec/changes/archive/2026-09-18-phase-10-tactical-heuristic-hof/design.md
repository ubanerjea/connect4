## Context

See proposal.md — Why for motivation. The codebase entering Phase 10 has:
- `game/bots.py`: `heuristic_bot` (three-rule) and `random_mover`; both use `functools.partial(..., rng=self.rng)` binding in Population
- `storage/schema.py`: `_AGENT_MIGRATIONS` list pattern for additive column migrations; `_HISTORY_MIGRATIONS` for config history
- `evolution/population.py`: `_run_heuristic_challenges()`, `_recompute_fitness()` (two-track), `run_tick()` with established phase order
- `config.py`: `heuristic_fitness_weight` scalar field; `MUTABLE_FIELDS` tuple in `run_simulation.py`

## Goals / Non-Goals

**Goals:**
- Introduce `tactical_heuristic_bot` as a selectable challenge opponent without touching the match runner
- Replace static `heuristic_fitness_weight` with a rolling-window adaptive formula; keep the per-tick query cheap (single indexed SELECT LIMIT N)
- Add Hall of Fame as a new subsystem (table, per-tick challenges, maintenance event) that cleanly extends `run_tick()` without restructuring existing phases
- Enable live migration of Phase 9 databases to Phase 10 schema without data loss

**Non-Goals:**
- Running both basic and tactical bots in parallel per tick
- HoF-based crossover (using HoF members as sexual reproduction partners)
- Analytics chart changes
- `population_snapshots` column additions

## Decisions

### Tactical bot: inline fork detection via board mutation
Fork detection uses a temporary append/pop on `board._grid[col]` to simulate placing a stone, then counts `would_win(c, player)` over remaining legal columns. This avoids copying the board and keeps complexity at O(7 × 7) per call. Accessing `_grid` directly rather than going through a public copy API is consistent with how `heuristic_bot` already calls `would_win` — both are internal-to-module operations.

*Alternative considered*: Expose a `Board.copy()` for immutable simulation. Rejected because it adds allocations to an inner loop and `_grid` mutation+revert is already the pattern `would_win` itself uses internally.

### Bot selection: get_heuristic_bot(level) factory
A `get_heuristic_bot(level: str) -> Callable` factory in `bots.py` returns the right function for `"basic"` or `"tactical"`. Population calls it once at construction/load time and stores the result, then passes it to `functools.partial` as before. The rest of the system is unaware of the distinction.

*Alternative considered*: Inline if/else in `_run_heuristic_challenges`. Rejected because the bot object is also needed for HoF maintenance candidate evaluation — a shared factory is cleaner.

### Adaptive weights: stateless formula recomputed from benchmark_results each tick
β_h and β_hof are not stored in simulation state; they are derived fresh in `_recompute_fitness()` from a rolling SELECT on `benchmark_results` filtered to `opponent_type = 'heuristic'` ORDER BY tick DESC LIMIT window. This stays correct across resumes with no additional persistence. The `idx_benchmark_results_tick` index (which may need adding if absent) keeps the query fast.

*Alternative considered*: Cache computed betas in Population and persist in simulation_state. Rejected because the benchmark table is the source of truth and a SELECT LIMIT 20 is negligible overhead vs. thousands of play_match calls per tick.

### Hall of Fame: separate table with agent_id foreign key
HoF members are rows in `hall_of_fame` referencing `agents.agent_id`. Genomes live in `agents.nn_weights` forever (dead agents are never deleted). HoF members are loaded at Population.load() into a list of Agent objects constructed from their stored weights — no genome duplication.

*Alternative considered*: Pickle/serialize the genome into hall_of_fame. Rejected because it creates a second copy that diverges from agents table and complicates the integrity story.

### HoF active member cache in Population
`Population` holds a list `self._hof_agents: list[Agent]` of reconstructed Agent objects for per-tick sampling. This list is updated (append on induction, remove on eviction) synchronously within `_run_hof_maintenance()`. At `Population.load()`, the list is rebuilt from `repo.list_hof_agents(status='active')`.

*Alternative considered*: Query the DB on every tick for active HoF members. Rejected because this adds a query per tick; the in-memory list is O(1) to sample and always consistent since maintenance is single-threaded.

### Maintenance games don't touch Population.alive counters
Maintenance (Steps 1–2) reconstructs HoF members as Agent objects but does NOT call `self._persist_stats()` or modify `self.alive`. Candidate evaluation (Step 3) plays games using the candidate's chooser but discards the result — the play_match return value is read-only. The invariant is enforced by never passing HoF member or candidate agent objects to `_persist_stats()` during maintenance.

### Config rename: heuristic_fitness_weight → heuristic_fitness_weight_max
`Config.from_dict()` will check for the old key and either alias it to the new key (reading the old value as `heuristic_fitness_weight_max`) or raise a descriptive error with migration instructions. The simulation_config_history schema adds a new column `heuristic_fitness_weight_max` via `_HISTORY_MIGRATIONS` while keeping `heuristic_fitness_weight` for backward-readable old rows.

## Risks / Trade-offs

**Tactical bot significantly harder than basic** → adaptive weight responds by keeping β_h high; if agents stall for thousands of ticks with near-zero heuristic wins, survival credit differentiates them but may compress the fitness distribution. Mitigation: reduce `heuristic_fitness_weight_min` to 0.2 or temporarily switch back to `"basic"` if the population cannot make progress.

**HoF cold start: no HoF games for first 50 ticks** → this is Phase 9 behavior; β_hof stays 0.0, formula is two-track. Not a regression, just a delayed ramp.

**Lifespan pressure at 6 games/tick steady state** → agents reach lifespan ceiling 3× faster than Phase 8. Mitigation: increase `lifespan_range` (e.g., `[100, 300]`) or `reproduction_interval_min` on resume if agents die too young for fitness to stabilize.

**HoF lock (all members above eviction margin)** → symptom is stable HoF with no new inductees despite population improvement. Mitigation: reduce `hof_eviction_margin` on resume.

**Compute cost ≈2× Phase 9** → steady-state ~2,524 games/tick; maintenance ticks add ~1,200-game burst. Acceptable at default settings; reduce `hof_maintenance_heuristic_games` or `hof_maintenance_peer_games` if wall-clock time is a constraint.

## Migration Plan

1. Schema: `create_schema()` adds `hall_of_fame` table via `CREATE TABLE IF NOT EXISTS`. Four new `agents` columns and config history columns are added via `_AGENT_MIGRATIONS` / `_HISTORY_MIGRATIONS` append — `ALTER TABLE ... ADD COLUMN` with `DEFAULT 0` is safe against existing rows.
2. Config: `heuristic_fitness_weight` key in old YAML/DB rows is aliased (or clearly error'd) to `heuristic_fitness_weight_max` in `Config.from_dict()` and `MUTABLE_FIELDS`.
3. Resume continuity: new HoF counters default to 0 on all existing agents; first tick after migration behaves identically to Phase 9 (no active HoF members, β_hof = 0.0).

Rollback: switch `heuristic_bot_level` to `"basic"` and set `hof_enabled: false` on resume to reproduce Phase 9 behavior from the same DB; no schema rollback needed.
