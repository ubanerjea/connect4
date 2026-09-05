## Purpose

A live, steady-state population of agents that plays games against itself, reproduces at fitness-driven intervals, dies by individual lifespan, stays within a carrying capacity, and records its state every tick.

## ADDED Requirements

### Requirement: Initial population creation
The system SHALL create an initial population of a configured size, each a freshly random agent with no parents, at generation zero.

#### Scenario: Fresh population has no parents
- **WHEN** a new population is created
- **THEN** it SHALL contain the configured number of agents, each with no parent references and generation zero

### Requirement: Alive agents are paired and play each tick
The system SHALL pair up currently-alive agents each tick and have each pair play two games, one with each agent moving first, leaving at most one agent unpaired if the alive count is odd.

#### Scenario: Every alive agent but at most one plays
- **WHEN** a tick runs with an odd number of alive agents
- **THEN** every agent SHALL be paired and play except at most one, which sits out that tick

#### Scenario: Each pair plays with both orderings
- **WHEN** a tick runs with a paired agent
- **THEN** that pair SHALL play exactly two games, one with each agent moving first

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
The system SHALL, whenever a reproduction event would push the population above its configured capacity, remove the lowest-fitness agent old enough to have a fair fitness estimate.

#### Scenario: Population never exceeds capacity after culling
- **WHEN** reproduction events occur repeatedly against a population at its capacity
- **THEN** the population's size SHALL never exceed that configured capacity

#### Scenario: Very young agents are protected from culling
- **WHEN** an agent has not yet played enough games to have a fair fitness estimate
- **THEN** it SHALL NOT be selected for culling

### Requirement: A population snapshot is recorded every tick
The system SHALL record a snapshot of population-wide statistics (size, fitness stats, average gene values) at the end of every tick.

#### Scenario: Snapshot reflects the tick just run
- **WHEN** a tick completes
- **THEN** a snapshot for that tick SHALL be recorded with the population's current size and fitness statistics
