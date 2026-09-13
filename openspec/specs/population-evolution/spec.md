# population-evolution Specification

## Purpose
A live, steady-state population of agents that plays games against itself, reproduces at fitness-driven intervals, dies by individual lifespan, stays within a carrying capacity, and records its state every tick.

## Requirements

### Requirement: Initial population creation
The system SHALL create an initial population of a configured size, each a freshly random agent with no parents, at generation zero.

#### Scenario: Fresh population has no parents
- **WHEN** a new population is created
- **THEN** it SHALL contain the configured number of agents, each with no parent references and generation zero

### Requirement: Alive agents are paired and play each tick
The system SHALL pair up currently-alive agents each tick and have each pair play exactly `games_per_pair_per_tick` games, alternating which agent moves first by game index (even-indexed game: agent A moves first; odd-indexed game: agent B moves first), leaving at most one agent unpaired if the alive count is odd.

#### Scenario: Every alive agent but at most one plays
- **WHEN** a tick runs with an odd number of alive agents
- **THEN** every agent SHALL be paired and play except at most one, which sits out that tick

#### Scenario: Each pair plays exactly the configured number of games
- **WHEN** a tick runs with a paired set of agents and `games_per_pair_per_tick` is set to N
- **THEN** each pair SHALL play exactly N games, alternating which agent moves first by game index

### Requirement: Games and stats are recorded
The system SHALL record each played game durably and update both participating agents' games-played and win/loss/draw counts accordingly.

#### Scenario: A win updates the winner's and loser's counters
- **WHEN** a game between two agents ends in a win for one of them
- **THEN** the winning agent's win count SHALL increase by one and the losing agent's loss count SHALL increase by one, and both agents' games-played counts SHALL increase by one

#### Scenario: A draw updates both agents' draw counters
- **WHEN** a game between two agents ends in a draw
- **THEN** both agents' draw counts SHALL increase by one, and both agents' games-played counts SHALL increase by one

### Requirement: Fitness reflects win rate
The system SHALL recompute each alive agent's overall fitness each tick using a two-track formula: peer fitness and heuristic fitness are each computed independently from their respective counter sets and blended using a configured weight β (`heuristic_fitness_weight`). Peer fitness counts draws as half a win against peer games played; heuristic fitness counts wins (1.0), draws (0.5), and accumulated survival credit (proportional to game length on losses) against heuristic games played. If either counter is zero, that track contributes 0.0 to the blend. The resulting overall fitness is bounded to `[0, 1]` by the formula's construction when all inputs are non-negative.

#### Scenario: Fitness matches the two-track formula
- **WHEN** an agent has known peer and heuristic counter values after a tick
- **THEN** its fitness SHALL equal `(1 − β) × peer_fitness + β × heuristic_fitness`, where `peer_fitness = (peer_wins + 0.5 × peer_draws) / peer_games_played` (or 0.0 if `peer_games_played = 0`) and `heuristic_fitness = (heuristic_wins + 0.5 × heuristic_draws + heuristic_survival_credit) / heuristic_games_played` (or 0.0 if `heuristic_games_played = 0`)

#### Scenario: Survival credit accrues only on heuristic losses
- **WHEN** a heuristic challenge game ends in a loss for the agent
- **THEN** the agent's `heuristic_survival_credit` SHALL increase by `α × num_moves / (board_columns × board_rows)`, and SHALL remain unchanged when the game ends in a win or draw

#### Scenario: Zero heuristic games degrades to peer-only fitness
- **WHEN** `heuristic_games_per_agent_per_tick` is 0 and an agent has played only peer games
- **THEN** its fitness SHALL equal `(1 − β) × peer_fitness`, with the heuristic track contributing 0.0

### Requirement: Reproduction is gated by a fitness-driven interval
The system SHALL allow an agent to reproduce only once the number of games it has played since its last reproduction reaches an interval determined by its own fitness, longer for lower fitness and shorter for higher fitness.

#### Scenario: A fitter agent reproduces sooner
- **WHEN** two agents have different fitness values
- **THEN** the fitter agent's required interval between reproductions SHALL be no longer than the less fit agent's

### Requirement: Reproduction produces a linked child
The system SHALL, when an agent reproduces, add a new agent to the population whose genome is derived from that agent (and possibly a second, tournament-selected agent), recorded with a reference to its parent(s).

#### Scenario: A child records its parent
- **WHEN** an agent reproduces alone, without crossover
- **THEN** the new agent SHALL reference that agent as its parent and no second parent

#### Scenario: A child from crossover records both parents
- **WHEN** an agent reproduces via crossover with a second, tournament-selected agent
- **THEN** the new agent SHALL reference both agents as its parents

### Requirement: An agent dies when it reaches its own lifespan
The system SHALL remove an agent from the active population once its games-played count reaches its own lifespan, while keeping its full record.

#### Scenario: A dead agent no longer plays
- **WHEN** an agent's games-played count reaches its lifespan during a tick
- **THEN** it SHALL no longer be paired for games in later ticks, and its record SHALL remain durably stored

### Requirement: Population size is capped by culling
The system SHALL, whenever a reproduction event pushes the alive population above its configured capacity, cull a variable number of agents determined by sampling a fraction from a configured range using a Beta distribution with configurable shape parameters. It SHALL select cull candidates from mature agents (those with games played at or above the reproduction eligibility floor) ranked by lowest fitness first (tier 1), and optionally extend to immature living agents ranked by lowest parent fitness when tier 1 cannot fill the quota and a config flag is enabled (tier 2).

#### Scenario: Population never exceeds configured capacity after culling
- **WHEN** reproduction events occur repeatedly against a population at its capacity
- **THEN** the population's alive count SHALL never exceed the configured capacity after each culling pass

#### Scenario: Very young agents are protected from tier-1 culling
- **WHEN** an agent has not yet played games equal to or above the reproduction eligibility floor
- **THEN** it SHALL NOT be selected as a tier-1 cull candidate

#### Scenario: At least one agent is culled when the trigger fires and eligible candidates exist
- **WHEN** a reproduction event triggers culling and at least one eligible candidate exists across both tiers
- **THEN** at least one agent SHALL be culled

#### Scenario: Cull count falls within configured fraction range
- **WHEN** culling is triggered repeatedly across many events
- **THEN** the number of agents culled in each event SHALL be no less than `ceil(cull_fraction_range[0] × alive_count)` and no more than `floor(cull_fraction_range[1] × alive_count)`, with a minimum of 1

#### Scenario: Tier-2 immature candidates are used only after tier 1 is exhausted
- **WHEN** `cull_allow_immature_offspring` is true and the tier-1 mature pool cannot fill the full cull quota
- **THEN** the system SHALL draw remaining candidates from immature living agents, ranked ascending by the parent fitness value cached on each candidate at the time it was born (average of both parents' fitness at birth for crossover children; single parent's fitness at birth for clones)

#### Scenario: Tier-2 is skipped when the config flag is off
- **WHEN** `cull_allow_immature_offspring` is false and the tier-1 mature pool cannot fill the full cull quota
- **THEN** the system SHALL cull only as many agents as the tier-1 pool provides, leaving the population temporarily above capacity without error

### Requirement: A population snapshot is recorded every tick
The system SHALL record a snapshot of population-wide statistics (size, fitness stats, average gene values) at the end of every tick.

#### Scenario: Snapshot reflects the tick just run
- **WHEN** a tick completes
- **THEN** a snapshot for that tick SHALL be recorded with the population's current size and fitness statistics

### Requirement: A population can be reconstructed from storage
The system SHALL be able to reconstruct a fully live, in-progress population entirely from previously stored records — every currently-alive agent (including its lineage, genome, live stats, and parent-average fitness), the current tick, and the random-number-generator continuation state — such that the reconstructed population can continue running ticks indistinguishably from the original in-memory population at the moment it was last persisted.

#### Scenario: All alive agents are restored
- **WHEN** a population with a mix of alive and dead agents is reconstructed from storage
- **THEN** the reconstructed population SHALL contain exactly the agents that were alive, with no dead agents included

#### Scenario: Restored agents preserve genome, lineage, and live stats
- **WHEN** an agent is reconstructed from storage
- **THEN** its genome, parent references, generation, parent-average fitness, and games-played/wins/losses/draws/fitness/games-since-last-reproduction SHALL all match the values it had when last persisted

#### Scenario: Restored population resumes ticking from the correct tick
- **WHEN** a population is reconstructed from storage
- **THEN** running a tick against it SHALL advance from the persisted current tick, not from zero

#### Scenario: Restored population preserves tier-2 cull ordering
- **WHEN** a reconstructed population's population cap is enforced and immature-offspring culling is enabled
- **THEN** immature agents SHALL be ranked for culling by their persisted parent-average fitness, not a value of zero

### Requirement: Every alive agent plays heuristic challenge games each tick
The system SHALL, after pairing games complete and before fitness is recomputed, have every currently-alive agent play exactly `heuristic_games_per_agent_per_tick` games against the heuristic bot, alternating which side moves first by game index, and SHALL update that agent's heuristic-track counters (`heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`), unified counters (`wins`, `losses`, `draws`, `games_played`, `games_since_last_reproduction`), and store each game durably. If `heuristic_games_per_agent_per_tick` is 0 the system SHALL skip this step entirely, producing no games and leaving all counters unchanged.

#### Scenario: Each alive agent plays the configured number of heuristic games
- **WHEN** a tick runs with `heuristic_games_per_agent_per_tick = N > 0` and M alive agents
- **THEN** exactly M × N heuristic challenge games SHALL be played and durably stored that tick, and every alive agent's `heuristic_games_played` SHALL increase by N

#### Scenario: Heuristic challenge games count toward `games_since_last_reproduction` and `games_played`
- **WHEN** an agent plays a heuristic challenge game
- **THEN** both its `games_since_last_reproduction` and its unified `games_played` SHALL increase by one, so heuristic games advance the reproduction and lifespan countdowns identically to peer games

#### Scenario: Disabling heuristic challenges restores Phase 8 behavior
- **WHEN** `heuristic_games_per_agent_per_tick` is 0
- **THEN** no heuristic challenge games SHALL be generated that tick, no heuristic-track counters SHALL change, the RNG state at tick end SHALL be identical to what it would be in a Phase 8 run with the same peer games, and overall fitness SHALL degrade cleanly to the peer-only signal

#### Scenario: Heuristic challenge games are recorded as a distinct game type
- **WHEN** heuristic challenge games are logged
- **THEN** they SHALL carry `game_type = 'evolution_heuristic'`, the agent's id in the first player slot, no second agent id, and `opponent_label = 'heuristic'`

#### Scenario: Heuristic challenge games do not affect the agent's benchmark or official evolution record
- **WHEN** the benchmarking step runs after heuristic challenges in the same tick
- **THEN** the benchmarked agent's `games_played`, `wins`, `losses`, `draws`, and `fitness` values SHALL reflect the heuristic challenge games that tick, but the benchmark result itself SHALL still not alter those counters further

### Requirement: A population reconstructed from storage restores heuristic-track counters
The system SHALL, when reconstructing a population from storage, restore every alive agent's heuristic-track counters (`peer_wins`, `peer_draws`, `peer_games_played`, `heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`) to the values they had when last persisted, so that two-track fitness computation produces identical results from the resumed population.

#### Scenario: Restored agents preserve heuristic-track counters
- **WHEN** a population containing agents with non-zero heuristic-track counter values is reconstructed from storage
- **THEN** every restored agent's heuristic-track counters SHALL match the values that were last persisted

#### Scenario: Resumed run reproduces tick-by-tick fitness values
- **WHEN** a run is paused after a tick and resumed, with heuristic challenges enabled
- **THEN** the fitness values computed in the first resumed tick SHALL be identical to those that would have been computed had the run not been paused

### Requirement: The current-best agent is periodically benchmarked against fixed opponents
The system SHALL, every `benchmark_every_n_ticks`, have the current-best-by-fitness alive agent (determined after that tick's reproduction, death, and culling) play `benchmark_games_per_opponent` games against each of a set of fixed baseline opponents, alternating which side moves first, record a benchmark result per opponent, and record the individual games durably — without altering the benchmarked agent's own official games-played, win, loss, draw, or fitness counters.

#### Scenario: Benchmark evaluation happens on schedule
- **WHEN** a tick's number is a multiple of `benchmark_every_n_ticks` and the population is not empty
- **THEN** the current-best-by-fitness alive agent SHALL play `benchmark_games_per_opponent` games against each fixed baseline opponent that tick

#### Scenario: Off-schedule ticks are not benchmarked
- **WHEN** a tick's number is not a multiple of `benchmark_every_n_ticks`
- **THEN** no benchmark evaluation SHALL occur that tick

#### Scenario: Benchmark games do not affect the agent's official record
- **WHEN** the current-best agent plays its scheduled benchmark games
- **THEN** its games-played, wins, losses, draws, and fitness SHALL be unchanged by those games

#### Scenario: A benchmark result is recorded per opponent
- **WHEN** a benchmark evaluation completes against one fixed opponent
- **THEN** a benchmark result SHALL be recorded reflecting that opponent's win rate over the games played
