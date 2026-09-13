## Context

See proposal.md — Why for motivation. The relevant current-state constraints:

- `_recompute_fitness()` currently uses a single unified formula: `(wins + 0.5 × draws) / games_played`. All game types (peer evolution only, at this point) feed the same counters.
- `run_tick()` order is: peer pairing → `_recompute_fitness()` → reproduction/death loop → `_run_benchmark()` → `_write_snapshot()` → `repo.commit()`.
- `_persist_stats()` in `population.py` calls `repo.update_agent_stats()`, which enumerates the mutable agent fields. Both must be extended for the new columns.
- `heuristic_bot` already accepts an `rng` parameter (Phase 6 added this for benchmark use). The same binding pattern is reused here.
- The `insert_game` invariant in `repository.py` currently validates that non-`'evolution'` game types have `player2_agent_id=None` and a non-null `opponent_label`. The new `'evolution_heuristic'` type fits this existing branch — only the allowlist of recognized non-evolution types needs to grow.
- SQLite's `ALTER TABLE ... ADD COLUMN` with a `DEFAULT` is safe for existing rows and is the standard migration path for additive schema changes.

## Goals / Non-Goals

**Goals:**
- All seven new counter fields (peer/heuristic split) are stored, restored on resume, and used in fitness computation.
- RNG state after a tick with heuristic challenges enabled is deterministic and reproducible across resume boundaries.
- Setting `heuristic_games_per_agent_per_tick=0` produces zero divergence from Phase 8 (no games, no counter changes, identical RNG state).
- All three new parameters (`heuristic_games_per_agent_per_tick`, `heuristic_survival_alpha`, `heuristic_fitness_weight`) are mutable on resume.

**Non-Goals:**
- Benchmark system changes — benchmarks remain an independent external validity check.
- Analytics chart changes — queryable via existing `games` and `agents` tables.
- `population_snapshots` column changes.

## Decisions

### Decision 1: Two-track fitness (Option C) over unified counters (Option B)

Option B (unified counters, no split) is simpler: add heuristic games to `wins`/`draws`/`games_played` and adjust β at the formula level. Option C (separate counter sets per track) is chosen because:

- **Independent scaling**: with a unified pool, heuristic volume directly dilutes peer fitness numerically even before β is applied. A 1:1 game ratio already makes each pool 50% of the signal before any weight is applied; changing game volumes would require retuning β. With split counters, β is the *only* knob for weighting — changing `heuristic_games_per_agent_per_tick` from 2 to 4 doesn't silently shift the effective weight.
- **Survival credit placement**: credit (a partial score on losses) belongs only in `heuristic_fitness`. Adding it to a unified pool with peer games would require a new column anyway and muddle the semantics of `wins`/`draws`.

**Alternative considered**: compute survival credit as a virtual adjustment at fitness-recompute time from raw counters, without a stored `heuristic_survival_credit` field. Rejected because it makes the stored counters insufficient to reproduce fitness independently (you'd need to replay all game lengths), which breaks the resume invariant without DB changes.

### Decision 2: Heuristic challenges execute after peer games, before `_recompute_fitness()`

This maximises selection tightness: heuristic results from tick T inform that tick's fitness, which drives that tick's reproduction and culling, not tick T+1's. The alternative (after `_recompute_fitness()`) would mean one-tick lag on heuristic feedback.

### Decision 3: Survival credit formula — `α × num_moves / 42`

`42 = board_columns × board_rows` (the maximum possible moves on a 7×6 board). Dividing by 42 bounds the credit to `[0, α]`, so with α=0.5 a full-board survival is worth as much as a draw. This anchors the credit to a physically meaningful reference (the board) rather than an empirical observed-game-length maximum, which could drift across populations.

### Decision 4: Schema migration via `ALTER TABLE ... ADD COLUMN`

`CREATE TABLE IF NOT EXISTS` in `schema.py` cannot add new columns to an existing table. The correct pattern for additive migrations in this codebase is `ALTER TABLE agents ADD COLUMN ... DEFAULT 0` statements guarded by existence checks (`SELECT COUNT(*) FROM pragma_table_info('agents') WHERE name = '...'`). This preserves all existing rows with zero defaults and requires no data migration.

For new databases the schema DDL must include the columns directly so `CREATE TABLE IF NOT EXISTS` produces the full table in one step.

### Decision 5: All three new parameters in `MUTABLE_FIELDS`, none in `FROZEN_FIELDS`

`heuristic_games_per_agent_per_tick`, `heuristic_survival_alpha`, and `heuristic_fitness_weight` affect the fitness signal going forward but do not change the genome structure or board representation. Allowing resume with different values is intentional — the disable path (`=0`) is only useful if it can be set on an existing run.

### Decision 6: `bound_heuristic = functools.partial(heuristic_bot, rng=self.rng)` per tick

Identical pattern to Phase 6's benchmark runner. Binding `self.rng` into the heuristic ensures that RNG calls inside `heuristic_bot` draw from the population's shared, persisted generator — required for bit-for-bit resume continuity. Creating the partial once at the top of `_run_heuristic_challenges()` (not per agent or per game) avoids the overhead of repeated partial object creation in the inner loop.

### Decision 7: Agent counters live on `Agent`, not inferred from the `games` table

The existing architecture keeps live stats on `Agent` objects (updated in `_record_game`) and uses `_persist_stats()` to flush them. The seven new counters follow the same pattern — no per-tick aggregate query against `games`. This preserves the existing performance model and the resume invariant (counters are persisted explicitly, not re-derived).

## Risks / Trade-offs

- **β too high suppresses peer signal** → start at β=0.7; monitor per-track fitness separately with a direct DB query if peer dynamics look degenerate.
- **`lifespan` and reproduction thresholds scale faster** — with 2 heuristic + 2 peer games per tick, agents hit their lifespan twice as fast as in Phase 8. `lifespan_range` defaults (`[30, 200]`) may need upward adjustment on existing runs. This is mutable, so it's a one-line config change; the risk is that runs started with the old defaults underexpose agents.
- **Schema migration ordering** — `_persist_stats()` must not be called before the schema migration runs. Since `Repository.__init__` calls `create_schema()`, which now includes the `ALTER TABLE` guards, migration always precedes any data operation.
- **Passive-strategy gaming** — agents could maximise game length by random non-blocking to accrue survival credit. Against the heuristic, extending a game requires active defence, so this is unlikely in practice; reduce α if it emerges.

## Migration Plan

1. `schema.py`: add seven new columns to the `CREATE TABLE agents` DDL and add `ALTER TABLE ... ADD COLUMN ... DEFAULT 0` guards for existing databases. On fresh runs the DDL produces the full table; on existing runs the `ALTER TABLE` statements add the columns with zero defaults.
2. `config.py` / `config.yaml`: add three new fields. Existing `load_config()` call sites continue to work — no new required arguments.
3. `agent.py`: add seven new counter attributes initialised to 0.
4. `repository.py`: extend `insert_agent`, `update_agent_stats`, `get_agent`, `list_agents`; add `'evolution_heuristic'` to the `insert_game` invariant.
5. `population.py`: add `_run_heuristic_challenges()`; update `_record_game()` to maintain peer-track counters alongside unified totals; update `_recompute_fitness()` for the two-track formula; update `load()` to restore new counters; call `_run_heuristic_challenges()` from `run_tick()` after peer pairing.
6. `run_simulation.py`: add three new entries to `MUTABLE_FIELDS`.

Rollback: setting `heuristic_games_per_agent_per_tick=0` in `config.yaml` on any existing run immediately disables heuristic challenges. The extra DB columns are inert when `heuristic_games_played=0` everywhere (overall fitness degrades to a peer-only signal). No DDL rollback is required for a running-system rollback.
