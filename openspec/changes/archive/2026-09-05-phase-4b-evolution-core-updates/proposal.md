## Why

Phase 4 built the simplest possible culling mechanism (always remove exactly one lowest-fitness eligible agent) as a deliberate placeholder, and accidentally left `games_per_pair_per_tick` wired to a hardcoded loop instead of the config value. This phase generalizes culling into a fully parametrized, Beta-distribution-controlled mechanism, fixes the config bug, and adds lineage fields to `Agent` in memory — all of which Phase 5's full integration depends on.

## What Changes

- **Bug fix**: `Population._play_pair` currently loops over `(1, -1)`, ignoring `config.games_per_pair_per_tick`; replace with a loop of exactly `config.games_per_pair_per_tick` iterations, alternating first-mover by iteration parity.
- **`Agent` lineage fields**: Add `parent1_id`, `parent2_id`, and `parent_avg_fitness` as optional constructor parameters on `Agent`, set at `Population._add_agent()` time. `parent1_id`/`parent2_id` mirror data already stored in the `agents` table (no new DB columns). `parent_avg_fitness` is the average of both parents' fitness at creation time for crossover children, the single parent's fitness for clones, and `0.0` for the initial population — stored only in memory, never in the DB.
- **Redesigned culling**: Replace `Population._enforce_population_cap()`'s single-agent cull with a variable-count cull drawn from a Beta-distribution-sampled fraction of the current alive population, with a configurable range and shape.
- **Optional tier-2 cull candidates**: When the mature-agent pool cannot fill the cull quota and a config flag is on, fill remaining slots from immature living agents ranked by `parent_avg_fitness` ascending — no DB reads required at cull time.
- **Four new config parameters**: `cull_fraction_range`, `cull_fraction_beta_a`, `cull_fraction_beta_b`, `cull_allow_immature_offspring` — all mutable/live (Phase 5 allowlist), never stored per-agent.

## Capabilities

### New Capabilities

_(none — all changes update existing behavior)_

### Modified Capabilities

- `population-evolution`: The population-cap requirement changes from "cull exactly one lowest-fitness eligible agent" to "cull a Beta-distributed variable count, with an optional second tier of immature candidates"; the pairing requirement changes to honor `games_per_pair_per_tick` instead of a fixed two-game loop.

## Impact

- `src/evoconnect4/agent/agent.py` — `Agent.__init__` gains `parent1_id`, `parent2_id`, and `parent_avg_fitness` parameters.
- `src/evoconnect4/evolution/population.py` — `_play_pair` loop and `_enforce_population_cap` are rewritten; no other methods change.
- `src/evoconnect4/config.py` — four new fields added to the `Config` dataclass.
- `config.yaml` — four new keys with specified defaults.
- `tests/test_agent.py` — updated for new constructor parameters.
- `tests/test_population.py` — new and updated tests for culling distribution, tier-2 activation, and games-per-pair count.
- No new external dependencies; Beta sampling uses `numpy.random.Generator.beta`, already present via `self.rng`.
