## Why

A 5500-tick run revealed that the closed-pool fitness signal is blind to actual game skill: heuristic win rate was 0.000 at 548 of 550 benchmark points, and a human could trivially beat the best agent by stacking four discs in the same column — because internal fitness averages at 0.5 by zero-sum arithmetic regardless of absolute strength. This is the Red Queen trap the project plan anticipated (§5, §14): agents optimise for beating their current pool-mates, not for playing Connect Four.

## What Changes

- **New config parameters**: `heuristic_games_per_agent_per_tick` (default 2), `heuristic_survival_alpha` α (default 0.5), `heuristic_fitness_weight` β (default 0.7) — all mutable on resume.
- **New tick step**: `_run_heuristic_challenges()` executes after peer games and before `_recompute_fitness()`, having every alive agent play the configured number of games against the heuristic bot each tick.
- **Two-track fitness formula**: peer games and heuristic games each maintain separate counter sets; overall fitness is `(1 − β) × peer_fitness + β × heuristic_fitness`, where `heuristic_fitness` counts survival credit on losses (`α × moves / 42`) in addition to wins (1.0) and draws (0.5).
- **Seven new `agents` table columns**: `peer_wins`, `peer_draws`, `peer_games_played`, `heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`. Existing unified columns (`wins`, `losses`, `draws`, `games_played`) are retained and continue to drive the lifespan countdown.
- **New `game_type`**: `'evolution_heuristic'` — admitted by the `insert_game` invariant alongside the existing `'evolution'`, `'benchmark'`, and `'human_vs_agent'` types.
- **Disable path**: setting `heuristic_games_per_agent_per_tick=0` causes `_run_heuristic_challenges()` to return immediately with no games generated and no counters touched, restoring Phase 8 behavior exactly.

## Capabilities

### New Capabilities

*(none — this change extends existing capabilities only)*

### Modified Capabilities

- `population-evolution`: fitness formula changes from a single unified win-rate to a two-track β-weighted formula; a new per-tick heuristic-challenge step introduces external selection pressure before `_recompute_fitness()`.
- `database-storage`: `agents` table gains seven new columns for the split fitness tracks; `insert_game` invariant is extended to admit `game_type='evolution_heuristic'` with a null second-player slot and `opponent_label='heuristic'`.

## Impact

- **`config.py` / `config.yaml`**: three new fields.
- **`storage/schema.py`**: seven new `agents` DDL columns.
- **`storage/repository.py`**: `insert_agent`, `update_agent_stats`, `get_agent`, `list_agents` updated for new columns; `insert_game` validation extended.
- **`agent/agent.py`**: seven new counter attributes.
- **`evolution/population.py`**: new `_run_heuristic_challenges()` method; `_record_game` updated to maintain peer-track counters; `_recompute_fitness()` updated for two-track formula; `load()` restores new counters; `run_tick()` call order updated.
- **`run_simulation.py`**: three new entries in `MUTABLE_FIELDS`.
- **`tests/`**: new tests for two-track fitness, survival credit, heuristic challenge game counts, `insert_game` invariant extension, resume continuity with new counters.
- No changes to `game/bots.py`, `game/match.py`, `interface/play_cli.py`, `analytics/`, or `population_snapshots`.
