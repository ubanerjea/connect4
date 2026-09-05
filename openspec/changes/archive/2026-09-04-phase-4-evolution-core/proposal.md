## Why

EvoConnect4 has a game engine (Phase 1), evolvable agents (Phase 2), and persistence (Phase 3), but nothing yet drives them together. Phase 4 of the plan's roadmap (§11) builds the evolution core: a live population that plays games, reproduces, dies, and stays within a carrying capacity — the steady-state tick loop described in §4.2.

## What Changes

- Extend `Agent` (Phase 2) with live-stats: `games_played`, `wins`, `losses`, `draws`, `fitness`, `games_since_last_reproduction` — matching plan §7's original file-tree comment for `agent.py` ("wraps a genome + network + live stats"), which Phase 2 deliberately deferred until a tick loop existed to give these fields meaning. `Agent` still does not gain mutable live weights for somatic mutation — that's Phase 9 (newly added to the roadmap during exploration), built once this core loop is proven on its own.
- Add `src/evoconnect4/evolution/population.py`: a `Population` that holds the live pool in memory, creates the initial random population (generation 0), and runs one tick (§4.2) — shuffles and pairs alive agents, plays 2 games per pair via Phase 1's `play_match` (both first-mover orderings), updates stats and writes games (Phase 3), recomputes fitness, checks reproduction eligibility via `reproduction_interval(fitness)` (§4.3) and tournament selection, builds children via Phase 2's already-existing `mutate()`/`crossover()`, checks death by lifespan (§4.4), culls the lowest-fitness agent when reproduction pushes the population over capacity (§4.5), and writes a population snapshot every tick (Phase 3). The benchmark-tick step in §4.2's pseudocode is skipped — that's Phase 6.
- No changes to the game engine, network/genome operators, or storage schema — this change is purely the orchestration layer wiring existing pieces together.

## Capabilities

### New Capabilities
- `population-evolution`: A live, steady-state population of agents that plays games, tracks each agent's own stats, reproduces at fitness-driven intervals, dies by individual lifespan, stays within a carrying capacity via culling, and records a snapshot of population state every tick.

### Modified Capabilities

None — `agent-genome`'s existing requirements (network forward pass, genome operations, always-legal move choice) are unchanged; live-stats is new observable behavior, captured under the new capability above rather than as a modification to `agent-genome`.

## Impact

- Modified files: `src/evoconnect4/agent/agent.py` (adds live-stats fields, no change to existing behavior or its constructor signature).
- New files: `src/evoconnect4/evolution/population.py`, `tests/test_population.py`.
- No new dependencies.
- No changes to `src/evoconnect4/game/`, `src/evoconnect4/agent/{network,genome}.py`, or `src/evoconnect4/storage/`.
