## 1. Schema and Storage Layer

- [x] 1.1 Add `hall_of_fame` table DDL to `_SCHEMA` in `storage/schema.py` with columns: `id`, `agent_id`, `inducted_tick`, `evicted_tick`, `status`, `heuristic_win_rate`, `internal_score`, `combined_score`. Verify `create_schema()` creates the table in a fresh DB and a Phase 9 DB gains the table via migration without data loss.

- [x] 1.2 Add four new agent column migrations to `_AGENT_MIGRATIONS` in `storage/schema.py`: `hof_wins INTEGER NOT NULL DEFAULT 0`, `hof_draws INTEGER NOT NULL DEFAULT 0`, `hof_games_played INTEGER NOT NULL DEFAULT 0`, `hof_survival_credit REAL NOT NULL DEFAULT 0.0`. Verify applying migrations against a Phase 9 DB adds the columns and all existing agent rows read zero for each.

- [x] 1.3 Add config history migration to `_HISTORY_MIGRATIONS` for the new HoF and adaptive weight params (rename `heuristic_fitness_weight` → `heuristic_fitness_weight_max`, add 13 new param columns). Verify history migration does not fail against a Phase 9 DB and old rows are readable with backward-compatible default values.

- [x] 1.4 Add `insert_hof(agent_id, inducted_tick, heuristic_win_rate)` and `list_hof_agents(status)` to `storage/repository.py`. Verify `list_hof_agents(status='active')` returns only active records and `list_hof_agents(status='evicted')` excludes active ones.

- [x] 1.5 Add `update_hof_heuristic_win_rate(hof_id, win_rate)` and `update_hof_scores(hof_id, internal_score, combined_score)` to `storage/repository.py`. Verify that reading the record after update reflects the new values.

- [x] 1.6 Add `evict_hof(hof_id, evicted_tick)` to `storage/repository.py`. Verify reading the record after eviction shows `status='evicted'` and the correct `evicted_tick`.

- [x] 1.7 Extend `insert_agent`, `update_agent_stats`, `get_agent`, and `list_agents` in `storage/repository.py` to include the four new HoF counter fields. Verify an agent inserted with non-zero HoF counters round-trips all four values correctly.

- [x] 1.8 Extend the `insert_game` invariant in `storage/repository.py` to accept `'hof_challenge'` (both player ids set, no opponent label), `'hof_maintenance_peer'` (both player ids set, no opponent label), and `'hof_maintenance_heuristic'` (first player id set, second null, opponent label = `'heuristic'`). Verify each new game type inserts successfully with the correct shape and is rejected with any incorrect shape.

## 2. Config

- [x] 2.1 Add 14 new fields to the `Config` dataclass in `config.py`: `heuristic_bot_level` (str, default `"tactical"`), `heuristic_fitness_weight_max` (float, default 0.7), `heuristic_fitness_weight_min` (float, default 0.3), `heuristic_weight_adapt_low` (float, default 0.60), `heuristic_weight_adapt_high` (float, default 0.90), `heuristic_weight_adapt_window` (int, default 20), `hof_enabled` (bool, default True), `hof_max_size` (int, default 20), `hof_games_per_agent_per_tick` (int, default 2), `hof_maintenance_every_n_ticks` (int, default 50), `hof_maintenance_heuristic_games` (int, default 20), `hof_maintenance_peer_games` (int, default 4), `hof_entry_heuristic_threshold` (float, default 0.70), `hof_eviction_margin` (float, default 0.15), `hof_fitness_weight_max` (float, default 0.4). Verify `Config.from_dict()` loads all new fields correctly from a dict with default values.

- [x] 2.2 Add backward compatibility handling in `Config.from_dict()` for the `heuristic_fitness_weight` rename: if the old key is present and the new key is absent, use the old value as `heuristic_fitness_weight_max`; if both are absent, use the default 0.7. Verify that a config dict with the old key correctly sets `heuristic_fitness_weight_max` and that a config dict with neither key uses the default.

- [x] 2.3 Update `config.yaml` to replace `heuristic_fitness_weight: 0.7` with `heuristic_fitness_weight_max: 0.7` and add all 14 new param entries. Verify the file loads without error and all new fields have the documented defaults.

- [x] 2.4 Update `MUTABLE_FIELDS` in `run_simulation.py` to remove `heuristic_fitness_weight` and add all 15 new/renamed fields. Verify that starting a run and changing any of the new fields mid-run via resume is accepted without a config validation error.

## 3. Agent Dataclass

- [x] 3.1 Add `hof_wins: int = 0`, `hof_draws: int = 0`, `hof_games_played: int = 0`, `hof_survival_credit: float = 0.0` to the `Agent` dataclass in `agent/agent.py`. Verify that constructing an Agent with no HoF kwargs results in all four counters at zero.

## 4. Tactical Heuristic Bot

- [x] 4.1 Implement `tactical_heuristic_bot(board, rng=None)` in `game/bots.py` using the five-rule priority order (win, block 1-ply win, create fork, block opponent fork, center preference). Fork detection uses inline `board._grid[col].append/pop` simulation and counts `would_win` over remaining legal columns. Add `get_heuristic_bot(level: str)` factory returning `heuristic_bot` for `"basic"` and `tactical_heuristic_bot` for `"tactical"`. Verify the function returns a legal column on an arbitrary mid-game board state.

- [x] 4.2 Write a unit test: provide a board position with an unambiguous fork-creating column for the current player (no immediate win, no 1-ply block needed) and assert `tactical_heuristic_bot` selects that column. Verify the test passes.

- [x] 4.3 Write a unit test: provide a board position where the opponent has a fork setup column (no higher-priority rule applies to the current player) and assert `tactical_heuristic_bot` selects the blocking column. Verify the test passes.

- [x] 4.4 Write a unit test: confirm `get_heuristic_bot("basic")` and `heuristic_bot` are the same function (or produce identical moves on a fixed board+RNG), and `get_heuristic_bot("tactical")` returns `tactical_heuristic_bot`. Verify the test passes.

## 5. Population: Adaptive Fitness and HoF Challenges

- [x] 5.1 Rewrite `_recompute_fitness()` in `evolution/population.py` to compute β_h and β_hof from the rolling window query (SELECT win_rate FROM benchmark_results WHERE opponent_type='heuristic' ORDER BY tick DESC LIMIT window), compute the three-track formula, and clamp β_hof to 0.0 when HoF has no active members. Verify via unit test: for `rolling_wr=0.0` the formula gives β_h=0.70, β_hof=0.00, β_peer=0.30 (default params); for `rolling_wr=0.75` gives β_h=0.50, β_hof=0.20, β_peer=0.30; for `rolling_wr=1.0` gives β_h=0.30, β_hof=0.40, β_peer=0.30; all sum to 1.0.

- [x] 5.2 Add `_run_hof_challenges()` to `evolution/population.py`. It samples active HoF members from `self._hof_agents` (with replacement if needed), plays `hof_games_per_agent_per_tick` games per alive agent alternating first-mover, updates `hof_wins`, `hof_draws`, `hof_games_played`, `hof_survival_credit`, unified `wins/losses/draws/games_played/games_since_last_reproduction`, calls `repo.insert_game(game_type='hof_challenge', ...)` and `_persist_stats()`. If `self._hof_agents` is empty or `hof_games_per_agent_per_tick == 0` it returns immediately. Verify: after a controlled tick with one active HoF member and N alive agents, `games_played` on each alive agent increases by `hof_games_per_agent_per_tick` beyond peer+heuristic baseline.

- [x] 5.3 Update `run_tick()` call order to: peer games → heuristic challenges → HoF challenges (`_run_hof_challenges`) → `_recompute_fitness()` → reproduction/death/culling → `_run_benchmark()` → `_run_hof_maintenance()` → `_write_snapshot()` → `repo.commit()`. Verify tick ordering by checking that `_run_hof_challenges` is called before `_recompute_fitness` and `_run_hof_maintenance` is called after `_run_benchmark` in `run_tick`.

- [x] 5.4 Update `_run_heuristic_challenges()` to use `get_heuristic_bot(self.config.heuristic_bot_level)` instead of the hardcoded `heuristic_bot` reference. Verify via unit test: with `heuristic_bot_level="basic"`, a controlled run produces identical RNG state and game counts to Phase 9 behavior.

## 6. Population: HoF Maintenance

- [x] 6.1 Add `_run_hof_maintenance()` to `evolution/population.py`. It shall: (1) skip unless `tick % hof_maintenance_every_n_ticks == 0` and `hof_enabled`; (2) re-evaluate each active member's heuristic win rate using `hof_maintenance_heuristic_games` games vs. the heuristic bot and call `repo.update_hof_heuristic_win_rate()`; (3) run intra-HoF random pairing using `hof_maintenance_peer_games` per pair and compute `internal_score` and `combined_score` for each member; (4) evaluate the best-alive-by-fitness candidate using `hof_maintenance_heuristic_games` games vs. the heuristic bot; (5) induct or evict+induct per the entry/eviction rules; (6) update `self._hof_agents` in memory. Log all maintenance games with the correct game types. Verify via unit test: maintenance games do NOT increment any alive agent's `games_played` or `games_since_last_reproduction`.

- [x] 6.2 Write a unit test for the entry path: with an empty HoF and a candidate whose win rate ≥ `hof_entry_heuristic_threshold`, confirm a new HoF row is created with status `'active'` after `_run_hof_maintenance()`. Verify the test passes.

- [x] 6.3 Write a unit test for the eviction path: with a full HoF (size = `hof_max_size`) and a candidate whose win rate exceeds the weakest member's by ≥ `hof_eviction_margin`, confirm the weakest member is evicted and the candidate is inducted. Verify the test passes.

- [x] 6.4 Write a unit test for the no-change path: with a full HoF and a candidate that does NOT exceed the weakest by the eviction margin, confirm no row changes status and no new row is added. Verify the test passes.

- [x] 6.5 Write a unit test confirming a currently-active HoF member that is also the best-alive agent is not inducted twice (guard against duplicate active row for same `agent_id`). Verify the test passes.

## 7. Population: Load and Resume

- [x] 7.1 Update `Population.load()` to restore the four HoF counters (`hof_wins`, `hof_draws`, `hof_games_played`, `hof_survival_credit`) for every alive agent from storage. Verify: pause a run after tick N, resume it, and confirm each alive agent's HoF counters match the values at pause.

- [x] 7.2 Update `Population.load()` to reconstruct active HoF members from `repo.list_hof_agents(status='active')` into `self._hof_agents` (loading genomes via `agents.nn_weights`). Verify: after load, a tick runs HoF challenge games immediately without requiring a maintenance cycle.

## 8. Integration and Definition of Done

- [x] 8.1 Run the full existing test suite and verify all tests pass with no regressions introduced by Phase 10 changes.

- [x] 8.2 Start a fresh run with `heuristic_bot_level: basic` and `hof_enabled: false` and verify via assertion or inspection that it produces identical tick-end game counts and fitness values to a Phase 9 equivalent (controlled RNG seed, same params otherwise).

- [x] 8.3 Start a short run (50+ ticks) with `heuristic_bot_level: tactical` and `hof_enabled: true`. After 50 ticks, confirm: the `hall_of_fame` table has at least one row if any candidate cleared `hof_entry_heuristic_threshold`; `hof_challenge` game records exist; `hof_maintenance_heuristic` and `hof_maintenance_peer` game records exist for tick 50; alive agent `hof_games_played` counters are non-zero. Verify by querying the DB.

- [x] 8.4 Resume a Phase 9 DB (`mygame_02.db`) with the new code and Phase 10 config. Verify: schema migrations run cleanly (no errors, no data loss); the run continues from the persisted tick; adaptive β values are logged and shift from the Phase 9 regime as the rolling window fills; heuristic win rate trend is observable after several hundred ticks.
