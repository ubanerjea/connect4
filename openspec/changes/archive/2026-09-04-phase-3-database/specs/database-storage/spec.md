## Purpose

Provides durable SQLite storage for agents, games, and population snapshots, so a running or completed simulation is a queryable history rather than only in-memory state.

## ADDED Requirements

### Requirement: Schema creation
The system SHALL create all tables required to store agents, games, and population snapshots (and a benchmark-results table reserved for future use) if they do not already exist.

#### Scenario: Fresh database gets all tables
- **WHEN** the storage layer is initialized against a fresh database
- **THEN** the agents, games, population_snapshots, and benchmark_results tables SHALL all exist afterward

### Requirement: Agent record round-trips faithfully
The system SHALL store an agent record and return an identical record when read back by its id.

#### Scenario: Inserted agent matches on read
- **WHEN** an agent record is inserted and then read back by its id
- **THEN** every field of the read record SHALL match the field values that were inserted

### Requirement: Agent genome data round-trips through storage
The system SHALL preserve a genome's weights and architecture exactly when stored and re-read as part of an agent record.

#### Scenario: Genome data survives a round trip
- **WHEN** an agent record carrying a genome's encoded weights and architecture is inserted and then read back
- **THEN** the decoded weights and architecture SHALL be identical to what was originally encoded

### Requirement: Agent records can be updated
The system SHALL allow an existing agent record's mutable fields (games played, wins, losses, draws, fitness, games since last reproduction, status, death cause) to be updated after insertion.

#### Scenario: Updating an agent persists the change
- **WHEN** an existing agent record's stats are updated
- **THEN** reading that agent back afterward SHALL reflect the updated values, not the original ones

### Requirement: Agent records can be listed and filtered by status
The system SHALL allow listing agent records filtered by status (alive or dead).

#### Scenario: Listing alive agents excludes dead ones
- **WHEN** agents with a mix of alive and dead status exist in storage
- **THEN** listing agents by alive status SHALL return only the alive ones

### Requirement: Game record round-trips faithfully
The system SHALL store a game record and return an identical record when read back by its id.

#### Scenario: Inserted game matches on read
- **WHEN** a game record is inserted and then read back by its id
- **THEN** every field of the read record, including its move history, SHALL match the values that were inserted

### Requirement: Game records can be listed by tick
The system SHALL allow listing all game records recorded for a given tick.

#### Scenario: Listing games for a tick returns only that tick's games
- **WHEN** games from multiple different ticks exist in storage
- **THEN** listing games for one specific tick SHALL return only the games recorded at that tick

### Requirement: Population snapshot round-trips faithfully
The system SHALL store a population snapshot and return an identical snapshot when read back.

#### Scenario: Inserted snapshot matches on read
- **WHEN** a population snapshot is inserted and then read back
- **THEN** every field of the read snapshot SHALL match the values that were inserted

### Requirement: The most recent population snapshot can be retrieved
The system SHALL allow retrieving the most recently recorded population snapshot.

#### Scenario: Latest snapshot reflects the most recent insert
- **WHEN** multiple population snapshots have been recorded at different ticks
- **THEN** retrieving the latest snapshot SHALL return the one with the highest tick
