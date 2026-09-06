## Purpose

Lets a human play a full, correctly-ruled game of Connect Four against any saved agent from a terminal, with results logged as an exhibition game that never affects the agent's official evolutionary record.

## ADDED Requirements

### Requirement: A saved agent can be selected by id or by fitness ranking
The system SHALL allow selecting the agent to play against either by its exact id, or by fitness ranking among currently-alive agents, or by fitness ranking among all agents ever recorded (alive or dead) in the target database.

#### Scenario: Selecting by id loads that exact agent
- **WHEN** an agent is selected by id
- **THEN** the system SHALL load that agent's stored genome, regardless of whether it is alive or dead

#### Scenario: Selecting by best-alive loads the fittest currently-alive agent
- **WHEN** an agent is selected by best-alive ranking
- **THEN** the system SHALL load the alive agent with the highest fitness

#### Scenario: Selecting by best-ever loads the fittest agent regardless of status
- **WHEN** an agent is selected by best-ever ranking
- **THEN** the system SHALL load the agent with the highest fitness among all agents ever recorded, including dead ones

#### Scenario: An unresolvable selection fails clearly
- **WHEN** a selection names an id that does not exist, or a fitness-ranking mode with no matching agents in the database
- **THEN** the system SHALL report a clear error and SHALL NOT proceed to start a game

### Requirement: Board dimensions come from the target database's recorded configuration
The system SHALL reconstruct the selected agent's game-playing network using the board dimensions recorded for that population, independent of whatever a live, separately-editable configuration file currently specifies.

#### Scenario: Reconstruction is unaffected by a differing live configuration
- **WHEN** an agent is loaded from a database whose recorded board dimensions differ from the current value of a separately-editable configuration file
- **THEN** the agent SHALL be reconstructed using the dimensions recorded in that database, not the separately-editable file

### Requirement: A human can play a full, correctly-ruled game against the loaded agent
The system SHALL alternate turns between the human and the loaded agent according to Connect Four's rules until the game ends in a win or a draw, rendering the current board position to the human before each of their moves and after the game ends.

#### Scenario: An illegal human move is rejected without ending the game
- **WHEN** the human enters a column that is out of range, not a number, or already full
- **THEN** the system SHALL reject that input, explain why, and prompt again without advancing the game

#### Scenario: A legal human move is applied and play continues
- **WHEN** the human enters a legal column
- **THEN** that move SHALL be applied and, if the game has not ended, play SHALL continue with the other participant's turn

#### Scenario: The game ends correctly on a win or a draw
- **WHEN** a move completes four in a row, or the board fills with no winner
- **THEN** the game SHALL end and the outcome SHALL be reported to the human

### Requirement: Who moves first is chosen before each game
The system SHALL ask the human, before each game, whether they want to move first.

#### Scenario: The human's choice determines the first move
- **WHEN** the human indicates they want to move first
- **THEN** the human SHALL make the game's first move; otherwise the agent SHALL make the first move

### Requirement: Completed games are logged as an exhibition, not counted toward the agent's official record
The system SHALL record every completed human-vs-agent game durably, identified as an exhibition game against a human-supplied name, and SHALL NOT alter the agent's official games-played, win, loss, draw, or fitness counters as a result.

#### Scenario: A completed game is recorded with the human's name
- **WHEN** a game between the human and the loaded agent completes
- **THEN** it SHALL be recorded as an exhibition game, associated with the name the human provided (or a default name if none was given)

#### Scenario: The agent's official record is unaffected
- **WHEN** one or more human-vs-agent games complete against a loaded agent
- **THEN** that agent's official games-played, win, loss, draw, and fitness counters SHALL remain exactly as they were before those games

### Requirement: The human can play multiple games in one session
The system SHALL, after each completed game, ask whether the human wants to play another game against the same loaded agent, continuing the session if so.

#### Scenario: Declining ends the session
- **WHEN** the human declines to play again
- **THEN** the session SHALL end without starting another game

### Requirement: The human can quit without a partial game being recorded
The system SHALL allow the human to quit at any point before a game ends, and SHALL NOT record that unfinished game.

#### Scenario: Quitting mid-game leaves no record of that game
- **WHEN** the human quits before a game reaches a win or a draw
- **THEN** the system SHALL end the session cleanly and no record of that unfinished game SHALL be created
