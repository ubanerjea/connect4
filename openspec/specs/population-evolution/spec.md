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
The system SHALL recompute each alive agent's fitness each tick as its win rate, counting a draw as half a win.

#### Scenario: Fitness matches the win-rate formula
- **WHEN** an agent's games-played, wins, and draws are known after a tick
- **THEN** its fitness SHALL equal (wins + 0.5 x draws) / games_played

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
