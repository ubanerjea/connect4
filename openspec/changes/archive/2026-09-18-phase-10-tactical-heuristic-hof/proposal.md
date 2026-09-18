## Why

After 6000 ticks on Phase 9, the heuristic challenge win rate hit 1.0 by tick 500 and stayed flat, removing all fitness gradient from the external challenge track — agents learned offensive fork-creation but never defensive blocking, because the fixed heuristic bot only creates 1-ply threats. Phase 10 restores a fitness gradient by upgrading the heuristic bot to create and block forks, making the challenge weight adaptive so it responds to mastery automatically, and introducing a Hall of Fame to keep the population's own best past agents as a standing self-challenge pool.

## What Changes

- **New bot**: `tactical_heuristic_bot` added to `game/bots.py`, selected via new `heuristic_bot_level` config param (`"basic"` = Phase 9 behavior, `"tactical"` = new fork-aware bot).
- **Adaptive fitness weights**: `heuristic_fitness_weight` (static) is renamed to `heuristic_fitness_weight_max` and the weight formula is replaced by an adaptive two-parameter system (β_h, β_hof) computed each tick from a rolling window of recent benchmark results.
- **Three-track fitness**: fitness formula extended from two tracks (peer + heuristic) to three (peer + heuristic + Hall of Fame), with adaptive β values that always sum to 1.
- **Hall of Fame table**: new `hall_of_fame` SQLite table storing references to inducted agents, their maintenance scores, and eviction status.
- **Four new agent counters**: `hof_wins`, `hof_draws`, `hof_games_played`, `hof_survival_credit` on the `agents` table.
- **Per-tick HoF challenges**: every alive agent plays `hof_games_per_agent_per_tick` games against randomly-sampled active HoF members each tick; these count toward `games_played` and `games_since_last_reproduction`.
- **HoF maintenance**: unified entry + eviction event every `hof_maintenance_every_n_ticks` ticks; evaluates HoF member health vs. heuristic and intra-HoF, then evaluates the current best-alive candidate for induction.
- **Three new game_type values**: `hof_challenge`, `hof_maintenance_heuristic`, `hof_maintenance_peer`; `insert_game` invariant extended accordingly.
- **Fourteen new config params + one rename**: all in `MUTABLE_FIELDS`. **BREAKING**: `heuristic_fitness_weight` key removed; must be aliased or emit a clear migration error on resume.

## Capabilities

### New Capabilities

- `hall-of-fame`: Maintains a persisted pool of the population's past-best agents (Hall of Fame), periodically evaluated for quality and rotated by entry/eviction rules, used as a standing challenge opponent for all alive agents each tick.
- `tactical-heuristic-bot`: A heuristic Connect 4 bot that extends Phase 9's three-rule priority order with fork-creation (rule 3) and fork-blocking (rule 4).

### Modified Capabilities

- `population-evolution`: Fitness formula changes from two-track static-weight to three-track adaptive-weight; `run_tick()` gains two new phases (HoF challenges, HoF maintenance); population reconstruction must restore four new HoF counters; heuristic bot selection is parameterized.
- `database-storage`: `hall_of_fame` table added; four new columns on `agents`; `insert_game` invariant extended with three new game types and mixed player-slot constraints for HoF games.

## Impact

- `config.yaml` / `config.py`: 14 new fields, 1 rename (breaking on resume from Phase 9 DB if the old key is present).
- `game/bots.py`: new `tactical_heuristic_bot` function and `get_heuristic_bot(level)` selector.
- `storage/schema.py`: DDL for `hall_of_fame` table; 4 new `agents` columns (added via `ALTER TABLE IF NOT EXISTS` for live migration).
- `storage/repository.py`: new HoF CRUD methods; `insert_agent`, `update_agent_stats`, `get_agent`, `list_agents` extended for new counters; `insert_game` updated.
- `agent/agent.py`: 4 new counter fields.
- `evolution/population.py`: `_run_hof_challenges()`, `_run_hof_maintenance()`, `_recompute_fitness()` (three-track adaptive), `load()` (new counters).
- `run_simulation.py`: `MUTABLE_FIELDS` update; `heuristic_fitness_weight` rename guard.
- No changes to `game/match.py`, `game/connect_four.py`, `interface/play_cli.py`, or `analytics/plots.py`.
- Compute cost approximately doubles vs. Phase 9 (steady-state ~2,524 games/tick with default HoF params).
