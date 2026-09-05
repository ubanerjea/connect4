## MODIFIED Requirements

### Requirement: Alive agents are paired and play each tick
The system SHALL pair up currently-alive agents each tick and have each pair play exactly `games_per_pair_per_tick` games, alternating which agent moves first by game index (even-indexed game: agent A moves first; odd-indexed game: agent B moves first), leaving at most one agent unpaired if the alive count is odd.

#### Scenario: Every alive agent but at most one plays
- **WHEN** a tick runs with an odd number of alive agents
- **THEN** every agent SHALL be paired and play except at most one, which sits out that tick

#### Scenario: Each pair plays exactly the configured number of games
- **WHEN** a tick runs with a paired set of agents and `games_per_pair_per_tick` is set to N
- **THEN** each pair SHALL play exactly N games, alternating which agent moves first by game index

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
