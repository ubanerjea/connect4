## Why

The population's own internal fitness is a relative, co-evolving signal that can plateau or cycle without genuine improvement. `benchmark_results` already exists in the schema (Phase 3) and `game/bots.py`'s `random_mover`/`heuristic_bot` already exist (Phase 1), but nothing writes to the table and nothing calls the bots from the tick loop — periodically checking the current-best agent against these fixed, non-co-evolving opponents is the real evidence evolution is working.

## What Changes

- Add a benchmark step to `Population.run_tick()`: every `benchmark_every_n_ticks`, the current-best-by-fitness alive agent plays `benchmark_games_per_opponent` games against each of the two fixed bots, alternating first-mover for fairness. Runs after that tick's reproduction/death/culling, before the snapshot write.
- Fix `random_mover`/`heuristic_bot` to accept an optional `rng: np.random.Generator | None = None` parameter (falling back to stdlib `random` when omitted, so existing callers/tests are unaffected). Benchmark calls bind `population.rng` — without this, benchmarking would silently break Phase 5's bit-for-bit resume guarantee for any run whose tick range crosses a benchmark boundary, since the bots currently consume Python's global unseeded `random` state instead of the tracked one.
- **BREAKING**: relax `games.player1_agent_id`/`player2_agent_id` from `NOT NULL` to nullable, and add a new `games.opponent_label TEXT` column, so benchmark (and later, Phase 8 human) games can be durably logged with full move history in the same unified table evolution games already use, instead of only an aggregate. No real `data/*.db` file exists yet in this repo, so there is no data to migrate.
- Add `Repository.insert_benchmark_result` / `Repository.list_benchmark_results(tick=...)`.
- Extend `Repository.insert_game` with optional `player2_agent_id`/`opponent_label` parameters, and add app-level (not database-`CHECK`-level) validation of the resulting invariant: `game_type='evolution'` requires both agent ids set and no label; any other `game_type` requires `player1_agent_id` set (the agent, always), `player2_agent_id` unset, and a label set.
- Add an `idx_games_game_type` index.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `database-storage`: `games` table's agent-id nullability and new `opponent_label` field; new `benchmark_results` round-trip/listing requirements; `insert_game`'s validated invariant across game types.
- `population-evolution`: adds the benchmark-evaluation step to the tick cycle.

## Impact

- `src/evoconnect4/game/bots.py` — `random_mover`/`heuristic_bot` gain an optional `rng` parameter.
- `src/evoconnect4/storage/schema.py` — `games` table: `player1_agent_id`/`player2_agent_id` become nullable, new `opponent_label` column, new `idx_games_game_type` index.
- `src/evoconnect4/storage/repository.py` — `insert_game` signature + validation; new `insert_benchmark_result`/`list_benchmark_results`.
- `src/evoconnect4/evolution/population.py` — new `_run_benchmark()`, called from `run_tick()`.
- No new external dependencies.
