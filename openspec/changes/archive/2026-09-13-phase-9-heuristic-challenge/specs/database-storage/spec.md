## ADDED Requirements

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

## MODIFIED Requirements

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
