## MODIFIED Requirements

### Requirement: Schema creation
The system SHALL create all tables required to store agents, games, population snapshots, and benchmark results if they do not already exist.

#### Scenario: Fresh database gets all tables
- **WHEN** the storage layer is initialized against a fresh database
- **THEN** the agents, games, population_snapshots, and benchmark_results tables SHALL all exist afterward

## ADDED Requirements

### Requirement: Game records support a single-agent opponent (benchmark or human)
The system SHALL allow a game record to represent either an agent-vs-agent evolution game (both player slots identify agents) or an agent-vs-non-agent game (exactly one player slot identifies the agent, the other left unset, with an opponent label identifying the non-agent opponent), and SHALL reject any other combination of agent ids and opponent label for a given game type.

#### Scenario: Evolution game requires both agent ids and no label
- **WHEN** a game record is inserted with game type 'evolution'
- **THEN** the system SHALL require both player agent ids to be set and no opponent label, rejecting the insert otherwise

#### Scenario: Non-evolution game requires exactly one agent id and a label
- **WHEN** a game record is inserted with a game type other than 'evolution'
- **THEN** the system SHALL require the first player slot to identify the agent, the second player slot to be unset, and an opponent label to be set, rejecting the insert otherwise

#### Scenario: Opponent label round-trips
- **WHEN** a non-evolution game record is inserted with an opponent label and later read back
- **THEN** the read record's opponent label SHALL match what was inserted

### Requirement: Benchmark results round-trip and can be listed
The system SHALL store a benchmark result (tick, agent, opponent type, games played, win rate) and allow listing benchmark results, optionally filtered by tick.

#### Scenario: Inserted benchmark result matches on read via listing
- **WHEN** a benchmark result is inserted and then listed
- **THEN** the listed record SHALL match the values that were inserted

#### Scenario: Listing filtered by tick returns only that tick's results
- **WHEN** benchmark results from multiple different ticks exist in storage
- **THEN** listing benchmark results for one specific tick SHALL return only the results recorded at that tick
