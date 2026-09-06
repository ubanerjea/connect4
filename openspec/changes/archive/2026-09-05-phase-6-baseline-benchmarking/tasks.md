## 1. Storage: schema changes

- [x] 1.1 In `src/evoconnect4/storage/schema.py`, relax `games.player1_agent_id`/`player2_agent_id` from `NOT NULL` to nullable, add a `opponent_label TEXT` column, and add `idx_games_game_type` alongside the existing `games` indices. Verify a fresh schema creation reflects all three changes (`PRAGMA table_info(games)` for nullability/column, `sqlite_master` for the index) and existing schema tests still pass.

## 2. Storage: repository CRUD

- [x] 2.1 Extend `Repository.insert_game` with `player2_agent_id: int | None = None` and `opponent_label: str | None = None`, and add app-level validation: `game_type='evolution'` requires both agent ids set and no label; any other `game_type` requires `player1_agent_id` set, `player2_agent_id` unset, and a label set — raise `ValueError` otherwise. Verify with tests covering both valid shapes and at least two invalid combinations (evolution missing an agent id; non-evolution with both agent ids set).
- [x] 2.2 Add `Repository.insert_benchmark_result(*, tick, agent_id, opponent_type, games_played, win_rate) -> int` and `Repository.list_benchmark_results(*, tick: int | None = None) -> list[dict]`, mirroring `insert_snapshot`/`list_games(tick=...)`'s existing style. Verify with a round-trip test and a test confirming the `tick` filter returns only that tick's results.

## 3. Bots: RNG determinism fix

- [x] 3.1 Add an optional `rng: np.random.Generator | None = None` parameter to `random_mover` and `heuristic_bot` in `src/evoconnect4/game/bots.py`, using `rng.choice(...)` (cast to plain `int`) when given, falling back to the existing `random.choice(...)` otherwise. Verify the three pre-existing bot tests (called with no `rng` argument) still pass unchanged, and add a test confirming two calls with the same seeded `rng` produce identical move sequences over repeated legal-move scenarios.

## 4. Population: benchmark step

- [x] 4.1 Implement `Population._run_benchmark()` per design.md's pseudocode: return early if `self.tick % config.benchmark_every_n_ticks != 0` or `self.alive` is empty; otherwise select the best-by-fitness alive agent and, for each of `(random_mover, "random")` and `(heuristic_bot, "heuristic")`, play `config.benchmark_games_per_opponent` games (agent always as `chooser_a`/`player1_agent_id`, bot bound to `self.rng` as `chooser_b`, alternating `first_mover` by game index), recording each game via `insert_game(game_type="benchmark", player2_agent_id=None, opponent_label=<opponent_type>)` and one `insert_benchmark_result` per opponent with the aggregated win rate — without calling `_persist_stats` or otherwise touching the benchmarked agent's own counters. Wire the call into `run_tick()` immediately after the reproduction/death loop, before `_write_snapshot()`.
- [x] 4.2 Verify with tests: a benchmark tick writes exactly 2 `benchmark_results` rows and `2 * benchmark_games_per_opponent` `games` rows; a non-benchmark tick writes neither; the benchmarked agent's `games_played`/`wins`/`losses`/`draws`/`fitness` are unchanged after its benchmark games; an empty population on a benchmark tick doesn't error.

## 5. Resume/reproducibility verification

- [x] 5.1 Extend Phase 5's bit-for-bit resume test coverage to a config with benchmarking enabled, using a `--ticks` split that crosses a `benchmark_every_n_ticks` boundary, and verify the split (paused-and-resumed) run's final state matches an uninterrupted continuous run with the same seed exactly — confirming the bot RNG fix actually preserves Phase 5's resume guarantee once benchmarking is active.

## 6. Full-suite verification

- [x] 6.1 Run the full existing test suite (`pytest`) and verify it still passes unchanged, confirming no regression to Phases 0-5.
