# Phase 6 — Baseline Benchmarking

*Scheduled evaluation of the population's current-best agent against fixed baseline bots, writing to `benchmark_results` — plus a `games` table schema change to keep every game type (evolution, benchmark, and eventually human) durably replayable in one unified log. See `evoconnect4_project_plan.md` §11.*

This document is a self-contained brief for entering the OpenSpec propose/apply cycle. It assumes Phases 0-5 are already built and archived — in particular Phase 1's `game/bots.py` (`random_mover`, `heuristic_bot`) and `game/match.py` (`play_match`), Phase 4/4b's tick loop, and Phase 5's RNG-continuity machinery (`population.rng`, resume semantics). `benchmark_every_n_ticks` and `benchmark_games_per_opponent` already exist in `config.yaml` from the original Phase 0 scaffolding — no new config fields are needed for this phase. No open questions remain — every decision below was explicitly resolved in the design conversation that produced this document.

## Why

The population's own internal fitness (§5) is a relative, co-evolving signal — it can plateau or cycle without genuine improvement (the "Red Queen" effect explicitly flagged in plan §5/§14). Fixed-baseline benchmarking is the intended fix: periodically check the current-best agent against opponents that never change, so a rising win-rate against them is real evidence evolution is working. `benchmark_results` already exists in the schema (Phase 3) but nothing writes to it, and nothing calls into `game/bots.py` from the tick loop yet.

## Scope

**In scope:**
1. A benchmark step in `Population.run_tick()`: every `benchmark_every_n_ticks`, the current-best-by-fitness alive agent plays `benchmark_games_per_opponent` games against each of the two fixed bots (`random_mover`, `heuristic_bot`), alternating first-mover for fairness (same treatment as evolution pairs).
2. `random_mover`/`heuristic_bot` gain an optional RNG parameter so benchmark ticks stay reproducible under Phase 5's resume/seed machinery, instead of silently depending on Python's global, unseeded `random` state.
3. `games` table schema change: `player1_agent_id`/`player2_agent_id` become nullable, and a new `opponent_label` column is added, so every game type — evolution, benchmark, and (later, Phase 8) human — can be durably logged with full move history in one unified table, not just an aggregate.
4. `Repository` CRUD for `benchmark_results` (`insert_benchmark_result`, `list_benchmark_results`) and the corresponding `insert_game` signature update.
5. App-level (not database-`CHECK`-level) validation of the new `games` invariant.

**Out of scope:**
- Any change to how fitness is computed or what counts toward it — benchmark games do **not** touch `agent.wins`/`losses`/`draws`/`games_played`/`fitness`, matching plan §5's explicit exclusion. Letting benchmark (or later, human) results feed into reproductive fitness is a deliberately deferred future extension — see plan §13 — not this phase.
- Switching fitness computation from incrementally-maintained counters to a live query over `games` — considered and explicitly rejected (tick-frequency performance cost, mid-tick availability before commit, and Phase 5 resume/load simplicity all favor staying counter-based).
- Phase 8's human-play CLI itself — this phase only makes sure the `games` schema is already shaped correctly for it.
- Any change to `population_snapshots` — untouched by this phase.

## Design: where the benchmark step lives

A new `Population._run_benchmark()`, called from `run_tick()` **after** the reproduction/death loop and **before** `_write_snapshot()` — matching plan §4.2's own pseudocode order, so "current best agent" means best-by-fitness *after* that tick's culling/deaths have already happened, not before.

```
IF self.tick % config.benchmark_every_n_ticks != 0: return
IF self.alive is empty: return   -- nothing to benchmark

best = max(self.alive, key=lambda a: a.fitness)

FOR (bot_fn, opponent_type) in [(random_mover, "random"), (heuristic_bot, "heuristic")]:
    bound_bot = bind bot_fn to self.rng (e.g. functools.partial or a small closure),
                so play_match still only ever sees a plain Board -> int callable --
                no change needed to match.py's Chooser contract
    wins = losses = draws = 0
    FOR i in range(config.benchmark_games_per_opponent):
        first_mover = 1 if i % 2 == 0 else -1
        result = play_match(best.choose_move, bound_bot, first_mover=first_mover)
        -- best.choose_move is always chooser_a (board position 1), bound_bot always
        -- chooser_b (board position -1), regardless of first_mover -- so result.winner==1
        -- always means "the agent won" here, independent of who moved first
        repo.insert_game(
            tick=self.tick, player1_agent_id=best.agent_id, player2_agent_id=None,
            result=<'player1_win'/'player2_win'/'draw' from result.winner>,
            num_moves=result.num_moves, move_history=result.move_history,
            game_type="benchmark", opponent_label=opponent_type,
        )
        tally wins/losses/draws (local only -- never touches best's own stats)

    win_rate = (wins + 0.5 * draws) / config.benchmark_games_per_opponent
    repo.insert_benchmark_result(
        tick=self.tick, agent_id=best.agent_id, opponent_type=opponent_type,
        games_played=config.benchmark_games_per_opponent, win_rate=win_rate,
    )
```

*(Pseudocode — an outline of the algorithm, not implementation, same convention as plan §4.2.)*

## `game/bots.py`: RNG determinism fix

`random_mover(board, rng=None)` / `heuristic_bot(board, rng=None)` — an optional `rng: np.random.Generator | None` parameter, defaulting to `None` (falls back to the existing stdlib `random.choice` calls, so the three existing bot tests keep passing unchanged). When benchmarking calls them, bind `population.rng` in before passing to `play_match` (a `functools.partial` or small closure keeps `match.py`'s `Chooser = Callable[[Board], int]` contract completely unchanged — no changes needed there). Cast `rng.choice(...)`'s result to a plain `int` for consistency with the existing return type. Without this fix, any run whose `--ticks` range crosses a `benchmark_every_n_ticks` boundary would silently break Phase 5's bit-for-bit resume guarantee, since the bots would be consuming Python's global unseeded RNG state instead of the tracked, persisted one.

## `games` table: nullable agent ids + `opponent_label`

```
games (revised)
+------------------------------------------------------------------------+
| game_type = 'evolution'                                                 |
|   player1_agent_id NOT NULL, player2_agent_id NOT NULL, label = NULL    |
|                                                                          |
| game_type = 'benchmark' / 'human_vs_agent' (Phase 8, later)             |
|   player1_agent_id = the agent (always)                                 |
|   player2_agent_id = NULL                                               |
|   opponent_label = 'random' | 'heuristic' | <human-entered name>        |
+------------------------------------------------------------------------+
```

- The agent always occupies `player1_agent_id` for non-evolution rows (never `player2_agent_id`) — this keeps `result` self-explanatory (`'player1_win'` always means "the agent won" for benchmark/human rows) and makes filtering trivial (`player2_agent_id IS NOT NULL` alone identifies an evolution game).
- `opponent_label` for benchmark rows must exactly match `benchmark_results.opponent_type`'s vocabulary (`'random'` / `'heuristic'`) — not a different naming scheme like `'random_mover'`/`'heuristic_bot'` — so the two tables stay joinable without a translation layer. For `human_vs_agent` (Phase 8, not this phase), `opponent_label` is genuinely free text.
- The invariant (evolution ⇒ both agent ids set, label null; non-evolution ⇒ player1 set, player2 null, label set) is validated in `Repository.insert_game` itself — a single choke point — and raises on violation, rather than a database `CHECK` constraint. Deliberate choice: neither `game_type` nor `result` has any DB-level enum enforcement today either (both are plain `TEXT NOT NULL`, vocabulary documented only in the plan), and app-level keeps the constraint logic simple and readable rather than an increasingly complex multi-column SQL `CHECK` expression.
- `player1_agent_id`/`player2_agent_id` losing their `NOT NULL` is a schema change to an existing, already-archived table. **BREAKING** in the same sense — and same accepted-trade-off reasoning — as Phase 5's `agents.parent_avg_fitness` addition: no `data/*.db` file exists yet in this repo, so there's no real data to migrate.
- Add `idx_games_game_type` alongside the existing `games` indices — filtering by game type becomes a real query pattern once benchmark/human rows share the table with evolution rows.

## `Repository` CRUD surface

```python
def insert_benchmark_result(
    self, *, tick: int, agent_id: int, opponent_type: str,
    games_played: int, win_rate: float,
) -> int: ...

def list_benchmark_results(self, *, tick: int | None = None) -> list[dict]: ...
```

`insert_benchmark_result` mirrors `insert_snapshot`'s style exactly. `list_benchmark_results(tick=...)` mirrors the existing `list_games(tick=...)`/`list_agents(status=...)` one-filter convention — a single optional `tick` filter covers "what happened at this specific benchmark point," and omitting it covers "give me the whole trend," which is what plan §9's chart (win-rate vs. random and vs. heuristic, over time) actually needs; with realistically tiny row counts (~2 rows per benchmark tick), grouping by `opponent_type`/`agent_id` at chart-build time in Python/pandas is simpler than adding more repository filter parameters for a case that doesn't need them.

`insert_game` gains `player2_agent_id: int | None = None` and `opponent_label: str | None = None` (both keyword, both optional, existing evolution-game call sites unaffected) and performs the invariant validation described above.

## Dependencies

Builds on Phase 1 (`game/bots.py`, `game/match.py`), Phase 3 (storage layer, `benchmark_results` table already exists), Phase 4/4b (tick loop), and Phase 5 (`population.rng` as the single reproducible RNG source — the bot fix specifically exists to preserve Phase 5's resume guarantees). No new external dependencies.

## Definition of done

- Matches plan §11's literal Phase 6 DoD: `benchmark_results` shows a visible trend over ticks.
- A benchmark tick writes exactly one `benchmark_results` row per opponent (`'random'`, `'heuristic'`) for the current-best agent, and each individual benchmark game is also recorded in `games` with `game_type='benchmark'`, `player2_agent_id` `NULL`, and `opponent_label` matching the same vocabulary.
- A unit test confirms benchmark games never change the benchmarked agent's `wins`/`losses`/`draws`/`games_played`/`fitness`.
- A unit test confirms `random_mover`/`heuristic_bot` produce identical move sequences across two runs given the same seeded `rng`, and that the three pre-existing bot tests (no `rng` argument) still pass unchanged.
- An extension of Phase 5's bit-for-bit resume test to a config with benchmarking enabled (a `--ticks` range crossing a `benchmark_every_n_ticks` boundary) confirms resume still continues identically.
- A test confirms `Repository.insert_game` rejects an invalid game_type/agent-id/opponent_label combination (e.g. `game_type='evolution'` with `player2_agent_id=None`, or `game_type='benchmark'` with both agent ids set).
- Full existing test suite continues to pass.

## Known limitations / deliberate trade-offs

- The `games` invariant is enforced only in `Repository.insert_game`, not at the SQLite schema level — a direct DB write bypassing the repository could violate it undetected. Accepted, per preference against complex multi-column `CHECK` constraints, and consistent with `game_type`/`result` already having no DB-level enum enforcement today.
- Benchmark games never influence reproductive fitness — deliberately excluded, matching plan §5. Counting them (or human games) toward fitness is noted as a possible future extension in plan §13, with its trade-offs, but not built here.
- Fitness stays counter-based, not derived by querying `games` — deliberate, for tick-frequency performance and Phase 5 resume/load simplicity.
