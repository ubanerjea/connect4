## 1. Config and Schema

- [x] 1.1 Add `heuristic_games_per_agent_per_tick: 2`, `heuristic_survival_alpha: 0.5`, and `heuristic_fitness_weight: 0.7` to `config.yaml`, then add the three corresponding typed fields to the `Config` dataclass in `config.py` and wire them in `load_config()`. Verify: `python -c "from evoconnect4.config import load_config; c = load_config(); assert c.heuristic_games_per_agent_per_tick == 2"` passes.

- [x] 1.2 Add the seven new columns (`peer_wins`, `peer_draws`, `peer_games_played`, `heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`) to the `CREATE TABLE agents` DDL in `schema.py` and add guarded `ALTER TABLE agents ADD COLUMN ... DEFAULT 0/0.0` migration statements for each so existing databases gain the columns on first connection. Verify: both a fresh database and a database created without the columns each have all seven columns after `create_schema()` runs.

## 2. Agent and Repository

- [x] 2.1 Add the seven new counter attributes to `Agent.__init__` (all initialised to 0 / 0.0), verify: `Agent` instantiation produces objects with all seven attributes at their zero defaults.

- [x] 2.2 Extend `Repository.insert_agent` to include all seven new columns with their zero defaults in the `INSERT` statement. Extend `Repository.update_agent_stats` to accept and persist all seven. Extend `_row_to_agent` (or equivalent), `get_agent`, and `list_agents` to return all seven columns. Verify: an agent inserted and read back via `get_agent` has all seven new fields present and equal to the inserted values; a `list_agents` call also returns them.

- [x] 2.3 Add `'evolution_heuristic'` to the `insert_game` invariant validation in `Repository.insert_game`, placing it in the non-evolution branch (requires `player2_agent_id=None` and a non-null `opponent_label`). Verify: `insert_game(..., game_type='evolution_heuristic', player1_agent_id=id, player2_agent_id=None, opponent_label='heuristic', ...)` succeeds; `insert_game(..., game_type='evolution_heuristic', player2_agent_id=id2, ...)` raises the existing validation error.

- [x] 2.4 Update `test_repository.py`: (a) extend the agent round-trip test to assert all seven new fields, (b) extend the `insert_game` invariant test to cover `game_type='evolution_heuristic'` accepting the correct shape and rejecting a non-null second agent id. Verify: all new test cases pass.

## 3. Evolution — Peer-Track Counters and Fitness Formula

- [x] 3.1 Update `Population._record_game()` to maintain peer-track counters alongside the existing unified counters: on a win increment `agent_a.peer_wins` and `agent_a.peer_games_played`; on a draw increment `agent.peer_draws` and `agent.peer_games_played` for both; on a loss increment only the losing agent's `peer_games_played`. Verify: after a controlled tick with two agents, each agent's `peer_games_played` equals `games_per_pair_per_tick` and `peer_wins + peer_draws + peer_losses == peer_games_played`.

- [x] 3.2 Replace the single-formula line in `Population._recompute_fitness()` with the three-line two-track formula: `peer_fitness`, `heuristic_fitness`, and `overall_fitness = (1 − β) × peer_fitness + β × heuristic_fitness`. Read β from `self.config.heuristic_fitness_weight`. Verify: unit test `test_population.py::test_two_track_fitness` constructs an agent with known counter values and asserts the resulting `fitness` matches the hand-calculated formula output.

## 4. Evolution — Heuristic Challenge Step

- [x] 4.1 Implement `Population._run_heuristic_challenges()` in `population.py`. The method SHALL: return immediately if `heuristic_games_per_agent_per_tick <= 0`; bind `heuristic_bot` to `self.rng` via `functools.partial`; iterate over every alive agent; play `heuristic_games_per_agent_per_tick` games per agent alternating first mover; update `heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit` (α × num_moves / 42 on losses), and the unified `wins`/`losses`/`draws`/`games_played`/`games_since_last_reproduction`; call `_persist_stats(agent)` after each game; call `repo.insert_game(..., game_type='evolution_heuristic', player1_agent_id=agent.agent_id, player2_agent_id=None, opponent_label='heuristic')` for each game. Verify: `test_population.py::test_heuristic_challenges_game_count` runs a one-tick simulation with `heuristic_games_per_agent_per_tick=2` and asserts every alive agent has `heuristic_games_played == 2` afterward and the `games` table contains exactly 2×N `evolution_heuristic` rows.

- [x] 4.2 Insert the call `self._run_heuristic_challenges()` into `Population.run_tick()` after the peer-pairing loop and before `self._recompute_fitness()`. Verify: the tick order matches the design (peer games → heuristic challenges → fitness → reproduction/death → benchmark → snapshot → commit), confirmed by running a 1-tick simulation and checking that `games_played` on every agent equals peer games + heuristic games played that tick.

- [x] 4.3 Add unit test `test_population.py::test_survival_credit_accrues_on_loss_only`: mock or control the match outcome so one game ends in a loss for the agent and another ends in a win; assert `heuristic_survival_credit` increased after the loss and is zero after the win; assert `heuristic_wins` is 1, `heuristic_survival_credit > 0`, and `heuristic_draws == 0`. Verify: test passes.

- [x] 4.4 Add unit test `test_population.py::test_heuristic_disable_no_side_effects`: run one tick with `heuristic_games_per_agent_per_tick=0`; assert no `evolution_heuristic` rows are in the `games` table, all heuristic-track counters are 0, and overall fitness equals `(1 − β) × peer_fitness`. Verify: test passes.

## 5. Population Resume

- [x] 5.1 Extend `Population.load()` to restore the seven new counters from the stored record for each alive agent. Verify: a population saved after one tick with `heuristic_games_per_agent_per_tick=2`, reconstructed via `load()`, produces agents with the same `heuristic_games_played`, `heuristic_wins`, `heuristic_draws`, `peer_wins`, `peer_draws`, `peer_games_played`, and `heuristic_survival_credit` as the original in-memory agents.

- [x] 5.2 Add resume test `test_population.py::test_heuristic_resume_continuity`: run a population for 3 ticks with `heuristic_games_per_agent_per_tick=2`, persist RNG state, reconstruct via `load()`, restore RNG state, run 2 more ticks; compare agent fitness values and counter sums against a continuous 5-tick run with the same seed. Verify: values match exactly.

## 6. Run Simulation

- [x] 6.1 Add `"heuristic_games_per_agent_per_tick"`, `"heuristic_survival_alpha"`, and `"heuristic_fitness_weight"` to the `MUTABLE_FIELDS` tuple in `run_simulation.py`. Verify: a resumed run that changes `heuristic_games_per_agent_per_tick` from 2 to 0 in `config.yaml` does not trigger a frozen-config mismatch error.

## 7. Integration and Full Test Suite

- [x] 7.1 Run the full test suite (`pytest`) and confirm all existing tests pass with the new code in place. Any regression in Phase 1–8 tests should be fixed before proceeding.

- [x] 7.2 Run a 50-tick smoke-test simulation with default config and verify: the `games` table contains `evolution_heuristic` rows (at least `50 × population_size × 2`), every alive agent has `heuristic_games_played > 0`, `population_snapshots` has 50 rows, and no uncaught exceptions occur.

- [x] 7.3 Run a 50-tick smoke-test with `heuristic_games_per_agent_per_tick=0` and verify: no `evolution_heuristic` rows exist in the `games` table, all heuristic-track agent columns are 0, and agent fitness values match the Phase 8 formula `(1 − β) × peer_fitness` (i.e., heuristic contributes 0.0). Confirm behavior is identical to a Phase 8 run by comparing overall fitness values against a reference run without the three new config fields.
