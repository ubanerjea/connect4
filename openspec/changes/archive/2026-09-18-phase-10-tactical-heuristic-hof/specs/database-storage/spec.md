## ADDED Requirements

### Requirement: Agent records carry HoF game counters
The system SHALL store, for each agent, four HoF counters: `hof_wins`, `hof_draws`, `hof_games_played`, and `hof_survival_credit`. These SHALL default to zero on insertion, round-trip faithfully through storage, and be included in every agent update operation alongside existing counters.

#### Scenario: New agent record has zero HoF counters
- **WHEN** an agent record is inserted (initial population or reproduction)
- **THEN** all four HoF counters SHALL be stored as zero and read back as zero

#### Scenario: HoF counters survive a round trip
- **WHEN** an agent record is inserted with non-zero HoF counter values and then read back
- **THEN** every HoF counter in the read record SHALL match the value that was inserted

#### Scenario: Updating an agent persists HoF counter changes
- **WHEN** an agent record's HoF counters are updated
- **THEN** reading that agent back SHALL reflect the updated values

#### Scenario: Existing databases gain HoF columns via migration
- **WHEN** the storage layer is initialized against a database that lacks the four HoF agent columns
- **THEN** those columns SHALL be added with DEFAULT 0 without altering any existing rows

### Requirement: Hall of Fame records round-trip faithfully
The system SHALL store a Hall of Fame record (member id, agent id, inducted tick, evicted tick, status, heuristic win rate, internal score, combined score) and return an identical record when read back.

#### Scenario: Inserted HoF record matches on read
- **WHEN** a HoF record is inserted and then read back
- **THEN** every field SHALL match the values that were inserted

### Requirement: Active HoF members can be listed
The system SHALL allow listing HoF records filtered by status (`'active'` or `'evicted'`).

#### Scenario: Listing active members excludes evicted ones
- **WHEN** the HoF contains a mix of active and evicted members
- **THEN** listing by status `'active'` SHALL return only active records

### Requirement: HoF member scores can be updated
The system SHALL allow updating a HoF member's `heuristic_win_rate`, `internal_score`, and `combined_score` after insertion, and SHALL allow marking a member as evicted with an eviction tick.

#### Scenario: Updating heuristic win rate persists the change
- **WHEN** a HoF member's `heuristic_win_rate` is updated
- **THEN** reading that member back SHALL reflect the new value

#### Scenario: Evicting a member updates status and evicted_tick
- **WHEN** a HoF member is evicted at tick T
- **THEN** reading that record back SHALL show `status = 'evicted'` and `evicted_tick = T`

## MODIFIED Requirements

### Requirement: Game records support a single-agent opponent (benchmark or human)
The system SHALL allow a game record to represent an agent-vs-agent evolution game (both player slots identify agents) or an agent-vs-non-agent game (exactly one player slot identifies the agent, the other left unset, with an opponent label), or a HoF challenge game (both player slots identify agents — one living agent and one HoF agent — with no opponent label), or a HoF maintenance peer game (both player slots identify HoF agents, no opponent label), or a HoF maintenance heuristic game (first player slot identifies a HoF agent, second unset, with opponent label). The system SHALL reject any combination of agent ids and opponent label that does not match a declared game type. Valid non-agent game types where second player is null are: `'benchmark'`, `'human_vs_agent'`, `'evolution_heuristic'`, `'hof_maintenance_heuristic'`. Valid agent-vs-agent game types where both player ids are set are: `'evolution'`, `'hof_challenge'`, `'hof_maintenance_peer'`.

#### Scenario: Evolution game requires both agent ids and no label
- **WHEN** a game record is inserted with game type `'evolution'`
- **THEN** the system SHALL require both player agent ids to be set and no opponent label, rejecting the insert otherwise

#### Scenario: Non-evolution single-agent game requires exactly one agent id and a label
- **WHEN** a game record is inserted with a game type in `{'benchmark', 'human_vs_agent', 'evolution_heuristic', 'hof_maintenance_heuristic'}`
- **THEN** the system SHALL require the first player slot to identify the agent, the second player slot to be unset, and an opponent label to be set, rejecting the insert otherwise

#### Scenario: hof_challenge game requires both agent ids and no label
- **WHEN** a game record is inserted with `game_type = 'hof_challenge'`
- **THEN** the system SHALL require both player agent ids to be set and no opponent label, rejecting the insert otherwise

#### Scenario: hof_maintenance_peer game requires both agent ids and no label
- **WHEN** a game record is inserted with `game_type = 'hof_maintenance_peer'`
- **THEN** the system SHALL require both player agent ids to be set and no opponent label, rejecting the insert otherwise

#### Scenario: hof_maintenance_heuristic game requires one agent id and a label
- **WHEN** a game record is inserted with `game_type = 'hof_maintenance_heuristic'`, a valid first-player agent id, no second agent id, and `opponent_label = 'heuristic'`
- **THEN** the insert SHALL succeed and the record SHALL round-trip with all fields intact

#### Scenario: Heuristic challenge game is accepted with the correct shape
- **WHEN** a game record is inserted with `game_type = 'evolution_heuristic'`, a valid first-player agent id, no second agent id, and `opponent_label = 'heuristic'`
- **THEN** the insert SHALL succeed and the record SHALL round-trip with all fields intact

#### Scenario: Opponent label round-trips
- **WHEN** a non-evolution single-agent game record is inserted with an opponent label and later read back
- **THEN** the read record's opponent label SHALL match what was inserted
