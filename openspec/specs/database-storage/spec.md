# database-storage Specification

## Purpose
Provides durable SQLite storage for agents, games, and population snapshots, so a running or completed simulation is a queryable history rather than only in-memory state.

## Requirements

### Requirement: Schema creation
The system SHALL create all tables required to store agents, games, population snapshots, and benchmark results if they do not already exist.

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

### Requirement: Population snapshots can be listed
The system SHALL allow listing all recorded population snapshots, ordered by tick, optionally filtered to a single tick.

#### Scenario: Listing all snapshots returns them in tick order
- **WHEN** multiple population snapshots have been recorded at different ticks
- **THEN** listing all snapshots SHALL return them ordered by tick

#### Scenario: Listing filtered by tick returns only that tick's snapshot
- **WHEN** population snapshots from multiple different ticks exist in storage
- **THEN** listing snapshots for one specific tick SHALL return only the snapshot recorded at that tick

### Requirement: Frozen simulation configuration is recorded once
The system SHALL store a single frozen-configuration record per database, written once when a population is first created, containing every configuration field never expected to change across that population's lifetime. This record also carries a `simulation_id` — a unique identifier assigned once at that same moment, used to identify this population's data across separate simulation databases.

#### Scenario: Frozen config is written on fresh population creation
- **WHEN** a new population is created in a fresh database
- **THEN** a frozen configuration record SHALL be stored containing that population's board dimensions, hidden layer sizes, and weight initialization std-dev

#### Scenario: Frozen config can be read back
- **WHEN** the frozen configuration record for a database is requested
- **THEN** it SHALL return the exact values recorded at population creation

#### Scenario: Each fresh population gets a unique, stable identifier
- **WHEN** a new population is created
- **THEN** the frozen configuration record SHALL include a `simulation_id` that is unique to that population and SHALL remain unchanged for the life of the database, including across any resume

### Requirement: Mutable configuration history is append-only
The system SHALL store a history of mutable configuration values, one entry per point at which the effective configuration changed, ordered by the tick at which each entry became effective.

#### Scenario: Initial mutable config is recorded at tick zero
- **WHEN** a new population is created
- **THEN** a history entry SHALL be recorded at tick zero containing the initial values of every mutable configuration field

#### Scenario: A later change appends a new entry without altering earlier ones
- **WHEN** a mutable configuration value changes at some later tick
- **THEN** a new history entry SHALL be recorded at that tick, and every earlier history entry SHALL remain unchanged

#### Scenario: The effective configuration at a given tick can be determined
- **WHEN** the mutable configuration is requested as of a specific tick
- **THEN** the system SHALL return the values from the most recent history entry at or before that tick

### Requirement: Simulation execution state can be persisted and restored
The system SHALL store the current tick count and the random-number-generator continuation state as a single, always-current record, overwritten on every update.

#### Scenario: Execution state reflects the latest update
- **WHEN** the execution state is updated with a tick count and RNG state
- **THEN** reading it back SHALL return exactly that tick count and RNG state, replacing whatever was stored before

### Requirement: Agent records carry parent-average fitness
The system SHALL store, for each agent, the average fitness of its parent(s) at the time of that agent's birth (the single parent's fitness for asexual reproduction, or the average of both parents' fitness for crossover), and SHALL return it unchanged on every subsequent read.

#### Scenario: Parent-average fitness round-trips
- **WHEN** an agent record is inserted with a parent-average-fitness value and later read back
- **THEN** the read record's parent-average-fitness SHALL match the value that was inserted

#### Scenario: Initial population agents have zero parent-average fitness
- **WHEN** an agent with no parents is inserted (the initial population)
- **THEN** its parent-average fitness SHALL be zero

### Requirement: Agent records carry split peer and heuristic game counters
The system SHALL store, for each agent, seven counters that separate peer-game and heuristic-game results: `peer_wins`, `peer_draws`, `peer_games_played`, `heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, and `heuristic_survival_credit`. These counters SHALL default to zero on insertion, round-trip faithfully through storage, and be included in every agent update operation alongside the existing unified counters.

#### Scenario: New agent record has zero heuristic-track counters
- **WHEN** an agent record is inserted (initial population or reproduction)
- **THEN** all seven heuristic-track counters SHALL be stored as zero and read back as zero

#### Scenario: Heuristic-track counters survive a round trip
- **WHEN** an agent record is inserted with non-zero heuristic-track counter values and then read back by its id
- **THEN** every heuristic-track counter in the read record SHALL match the value that was inserted

#### Scenario: Updating an agent persists heuristic-track counter changes
- **WHEN** an agent record's heuristic-track counters are updated
- **THEN** reading that agent back afterward SHALL reflect the updated counter values, not the original zeros

#### Scenario: Listing alive agents includes heuristic-track counter values
- **WHEN** alive agents are listed
- **THEN** each returned record SHALL include all seven heuristic-track counter fields with their current stored values

### Requirement: Game records support a single-agent opponent (benchmark or human)
The system SHALL allow a game record to represent either an agent-vs-agent evolution game (both player slots identify agents) or an agent-vs-non-agent game (exactly one player slot identifies the agent, the other left unset, with an opponent label identifying the non-agent opponent), and SHALL reject any other combination of agent ids and opponent label for a given game type. Valid non-agent game types are `'benchmark'`, `'human_vs_agent'`, and `'evolution_heuristic'`.

#### Scenario: Evolution game requires both agent ids and no label
- **WHEN** a game record is inserted with game type `'evolution'`
- **THEN** the system SHALL require both player agent ids to be set and no opponent label, rejecting the insert otherwise

#### Scenario: Non-evolution game requires exactly one agent id and a label
- **WHEN** a game record is inserted with a game type other than `'evolution'` (including `'benchmark'`, `'human_vs_agent'`, or `'evolution_heuristic'`)
- **THEN** the system SHALL require the first player slot to identify the agent, the second player slot to be unset, and an opponent label to be set, rejecting the insert otherwise

#### Scenario: Heuristic challenge game is accepted with the correct shape
- **WHEN** a game record is inserted with `game_type = 'evolution_heuristic'`, a valid first-player agent id, no second agent id, and `opponent_label = 'heuristic'`
- **THEN** the insert SHALL succeed and the record SHALL round-trip with all fields intact

#### Scenario: Heuristic challenge game with a second agent id is rejected
- **WHEN** a game record is inserted with `game_type = 'evolution_heuristic'` and a non-null second player agent id
- **THEN** the system SHALL reject the insert

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
