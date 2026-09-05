## ADDED Requirements

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
