## Why

`run_simulation.py` is still the Phase 0 stub (loads config, imports subpackages, prints settings, exits) even though every piece needed for a real run — game engine, evolvable agents, storage, and a working tick loop with Phase 4b's parametrized culling — is already built and archived. Wiring it into a real entry point surfaces three questions the plan never answered because they only make sense once there's something to actually invoke: how long does one run last, what happens to the database across repeated invocations, and how much reproducibility does a resumed run actually get.

## What Changes

- Add CLI arguments to `run_simulation.py`: `--ticks` (default 500), `--seed` (override), `--db` (target database path, default auto-timestamped).
- Add fresh-vs-resume decision logic: a target `--db` path with an existing live population resumes it; anything else starts a fresh population at that path.
- Add three new storage pieces: `simulation_config` (frozen, single row — including a `simulation_id` assigned once at fresh population creation, the stable key Phase 7's cross-simulation catalog keys its rollups and idempotency checks on), `simulation_config_history` (mutable, append-only), `simulation_state` (current tick + RNG continuation state, single row, always overwritten).
- Add a `parent_avg_fitness` column to the `agents` table and populate it on insert. **BREAKING** (schema change to an existing table — no migration path is provided; see design.md for why this is acceptable at this project's stage). This closes a gap found while grounding this proposal in the current code: `Agent.parent_avg_fitness` (used by Phase 4b's tier-2 immature-offspring culling) is currently computed at birth and kept only in memory, never persisted — so a resumed population would silently lose it and cull tier 2 by a fitness value of `0.0` for every pre-resume agent instead of its real parent-average fitness.
- Add `Population.load(config, repo)` — the resume counterpart to the existing `initialize()`, reconstructing a live population from stored agent records via the existing `Genome.decode()`/`Agent` round-trip machinery.
- Add resume-time validation of frozen config fields (`board_columns`, `board_rows`, `hidden_layer_sizes`, `weight_init_std`, plus any future config field not explicitly classified as mutable) against the `simulation_config` row already in the target database — a hard refusal (not a warning) on any mismatch, naming every mismatched field.
- Add RNG-state persistence (`numpy.random.Generator.bit_generator.state`, JSON-serialized) for exact resume continuity, with an explicit `--seed` override path to deliberately branch to a new seed at resume time instead of continuing the old stream.

## Capabilities

### New Capabilities
- `run-lifecycle`: the `run_simulation.py` CLI entry point's fresh-vs-resume decision, seed/RNG continuity rules, and resume-time frozen-config validation.

### Modified Capabilities
- `database-storage`: adds `simulation_config` (including a `simulation_id` assigned once at creation), `simulation_config_history`, and `simulation_state` tables with their CRUD, and adds the `parent_avg_fitness` field to the agent record contract.
- `population-evolution`: adds `Population.load()` as the resume counterpart to `initialize()`, reconstructing an in-progress population (including tier-2 cull ordering data) from storage.

## Impact

- `src/evoconnect4/run_simulation.py` — replaced with a real CLI entry point (argparse; no new dependency).
- `src/evoconnect4/storage/schema.py` — three new tables; `agents` table gains `parent_avg_fitness`.
- `src/evoconnect4/storage/repository.py` — CRUD for the three new tables; `insert_agent`/`_row_to_agent` gain `parent_avg_fitness`.
- `src/evoconnect4/evolution/population.py` — new `Population.load()`; `_add_agent`/`initialize()` unchanged in behavior but now feed the frozen/history config snapshot on population creation.
- `src/evoconnect4/agent/agent.py` — no change (already carries `parent_avg_fitness` in memory from Phase 4b).
- No new external dependencies — RNG state serialization uses `json` (stdlib) and `numpy.random.Generator.bit_generator.state`, already available via the existing `numpy` dependency.
