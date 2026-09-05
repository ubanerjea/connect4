## 1. Agent Live-Stats

- [x] 1.1 Extend `Agent.__init__` to initialize `games_played=0`, `wins=0`, `losses=0`, `draws=0`, `fitness=0.0`, `games_since_last_reproduction=0`, and verify a unit test constructs an `Agent` and reads back these fields at their zero defaults

## 2. Population Core

- [x] 2.1 Implement `Population(config, repo, rng=None)` with an `initialize()` that creates `config.population_size` random agents (via `genome.random_genome` + `Agent`), inserts each into `Repository` as generation 0 with no parents and `birth_tick=0`, and commits once, and verify a unit test confirms the correct agent count exists both in-memory and via `repo.list_agents`, each with generation 0 and no parent references

## 3. Tick Loop: Pairing & Games

- [x] 3.1 Implement pairing: shuffle alive agents using the population's `rng`, pair consecutively, leave the odd one out if the count is odd, and verify a unit test with an odd-sized population confirms exactly one agent is unpaired for that tick
- [x] 3.2 Implement per-pair game play — two calls to `play_match` (`first_mover=1` then `first_mover=-1`) and insert each game via `repository.insert_game` (`game_type='evolution'`) — and verify a unit test confirms two games are recorded per pair with populated move history

## 4. Tick Loop: Stats & Fitness

- [x] 4.1 Implement per-game stat updates (games played, wins/losses/draws) for both participating agents in memory, persisted via `repository.update_agent_stats`, and verify a unit test runs one tick and confirms both agents' in-memory and stored stats reflect the games played
- [x] 4.2 Implement fitness recomputation for every alive agent each tick as `(wins + 0.5 x draws) / games_played`, and verify a unit test asserts fitness matches the formula after a tick

## 5. Reproduction

- [x] 5.1 Implement `reproduction_interval(fitness)` per §4.3's formula, clamped to `config.reproduction_interval_min`/`_max`, and verify a unit test confirms higher fitness yields a shorter-or-equal interval than lower fitness
- [x] 5.2 Implement tournament selection (sample up to `min(tournament_size, len(alive) - 1)` other agents, excluding the reproducing agent, take the fittest) and the reproduction-eligibility check (`games_since_last_reproduction >= reproduction_interval(fitness)`), and verify a unit test with a manufactured eligible agent confirms a child is produced
- [x] 5.3 Implement child creation via the existing `genome.mutate()`/`crossover()` (combine per the parent's `crossover_rate`, always mutate afterward), inserting the new agent (generation = max parent generation + 1, `birth_tick` = current tick, parent references set, live-stats zeroed) into both the in-memory population and `Repository`, and reset the reproducing parent's `games_since_last_reproduction` to 0, and verify unit tests confirm a cloned child has one parent, a crossover child has two parents, and the reproducing parent's counter resets

## 6. Death

- [x] 6.1 Implement death — an agent whose `games_played` reaches its own `lifespan` is marked dead via `repository.mark_agent_dead` and removed from the in-memory alive pool — and verify a unit test confirms a manufactured agent at its lifespan is dead afterward and excluded from the next tick's pairing

## 7. Population Cap

- [x] 7.1 Implement culling — after each reproduction event, if the alive count exceeds `config.population_size`, mark dead (`death_cause='culled'`) the lowest-fitness agent among those with `games_played >= config.reproduction_interval_min` — and verify a unit test at capacity confirms population size never exceeds the cap after reproduction, and confirms an agent below that games-played threshold is never culled

## 8. Snapshot

- [x] 8.1 Implement a per-tick population snapshot (size, avg/max/min fitness, avg lifespan, avg mutation rate, best agent id) written via `repository.insert_snapshot`, and verify a unit test runs a tick and confirms a snapshot exists matching the population's current size

## 9. Full Tick Assembly & DoD

- [x] 9.1 Implement `Population.run_tick()` assembling groups 3-8 in order (pairing/games → stats/fitness → reproduction → death → culling → snapshot), committing once at the end, and verify a unit test runs a single tick end-to-end without error
- [x] 9.2 Verify plan §11's Phase 4 roadmap bar is met — a 50-tick run on a small population (e.g. 20 agents) shows plausible births and deaths occurring, with population size never exceeding its configured capacity throughout

## 10. Full Suite Verification

- [x] 10.1 Verify `uv run pytest` passes across `tests/test_population.py`, the updated `tests/test_agent.py`, and all existing tests with zero failures
