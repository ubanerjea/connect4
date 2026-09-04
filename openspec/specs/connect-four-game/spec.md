# connect-four-game Specification

## Purpose
Lets any two move-choosing strategies play a complete, correctly-ruled game of Connect Four — tracking board state, enforcing legal moves, detecting wins and draws, and reporting the outcome.

## Requirements

### Requirement: Board initialization
The system SHALL initialize a new game board as an empty grid of a configured width and height (7 columns by 6 rows by default), with no pieces placed.

#### Scenario: New game starts empty
- **WHEN** a new board is created with default settings
- **THEN** the board has 7 columns and 6 rows, and every cell is empty

### Requirement: Legal move tracking
The system SHALL identify which columns currently accept a move.

#### Scenario: Full column is not legal
- **WHEN** a column has been filled to its row capacity
- **THEN** that column SHALL NOT appear among the legal moves

#### Scenario: Non-full column is legal
- **WHEN** a column has at least one empty cell
- **THEN** that column SHALL appear among the legal moves

### Requirement: Move application obeys gravity
The system SHALL place a dropped piece in the lowest empty row of the chosen column.

#### Scenario: Piece settles to the bottom
- **WHEN** a player drops a piece into a column that already has pieces at the bottom
- **THEN** the new piece SHALL occupy the lowest empty cell in that column

### Requirement: Illegal moves are rejected
The system SHALL reject a move to a full or out-of-range column, and board state SHALL NOT change as a result.

#### Scenario: Move to full column rejected
- **WHEN** a player attempts to drop a piece into a column that is already full
- **THEN** the system SHALL reject the move and the board state SHALL remain unchanged

#### Scenario: Move to out-of-range column rejected
- **WHEN** a player attempts to drop a piece into a column index outside the board's valid range
- **THEN** the system SHALL reject the move and the board state SHALL remain unchanged

### Requirement: Win detection covers all four directions
The system SHALL detect four-in-a-row for the player who just moved, checked horizontally, vertically, and along both diagonal directions.

#### Scenario: Horizontal win
- **WHEN** a player has four of their pieces consecutive in a single row
- **THEN** the system SHALL report that player as the winner

#### Scenario: Vertical win
- **WHEN** a player has four of their pieces consecutive in a single column
- **THEN** the system SHALL report that player as the winner

#### Scenario: Diagonal win, ascending
- **WHEN** a player has four of their pieces consecutive along a diagonal rising left-to-right
- **THEN** the system SHALL report that player as the winner

#### Scenario: Diagonal win, descending
- **WHEN** a player has four of their pieces consecutive along a diagonal falling left-to-right
- **THEN** the system SHALL report that player as the winner

### Requirement: Draw detection
The system SHALL report a draw when the board is completely full and neither player has achieved four in a row.

#### Scenario: Full board with no winner is a draw
- **WHEN** every column is full and no player has four in a row
- **THEN** the system SHALL report the game as a draw, not as ongoing

### Requirement: Turn alternation
The system SHALL alternate which player is to move after each accepted move, starting from a designated first mover.

#### Scenario: Turn passes after a move
- **WHEN** a player successfully drops a piece and the game has not ended
- **THEN** the other player SHALL be the one to move next

### Requirement: Random mover always chooses legally
The system SHALL provide a move-choosing strategy that selects uniformly at random among the currently legal columns.

#### Scenario: Random mover respects legality
- **WHEN** the random-mover strategy is asked to choose a move on a board with at least one legal column
- **THEN** it SHALL return a column that is among the currently legal moves

### Requirement: Heuristic bot takes an immediate win
The system SHALL provide a move-choosing strategy that, when a legal move would complete four in a row for itself, chooses that move.

#### Scenario: Winning move is taken when available
- **WHEN** the heuristic-bot strategy is asked to choose a move and at least one legal column would immediately win the game for it
- **THEN** it SHALL choose one such winning column

### Requirement: Heuristic bot blocks an immediate opponent win
The system SHALL provide a move-choosing strategy that, when it has no immediate winning move but the opponent has a legal move that would win next turn, blocks that move.

#### Scenario: Blocking move is taken when no win is available
- **WHEN** the heuristic-bot strategy has no immediate winning move, and the opponent has exactly one column that would win for them next turn
- **THEN** it SHALL choose that column to block it

### Requirement: Heuristic bot prefers central columns otherwise
The system SHALL provide a move-choosing strategy that, absent an immediate win or block, prefers columns closer to the board's center, breaking ties randomly.

#### Scenario: Center preferred with no win or block available
- **WHEN** the heuristic-bot strategy has no immediate winning move and no immediate block available
- **THEN** it SHALL choose a legal column at least as close to the center column as any other legal column

### Requirement: Match runner plays a complete game
The system SHALL play a full game between two move-choosing strategies, alternating turns from a specified first mover, until a win or draw is reached, and SHALL report the outcome and the full sequence of moves played.

#### Scenario: Match reports the winner
- **WHEN** a match is played between two strategies and one of them achieves four in a row
- **THEN** the match result SHALL identify that player as the winner and SHALL include the full sequence of columns played

#### Scenario: Match reports a draw
- **WHEN** a match is played between two strategies and the board fills with no winner
- **THEN** the match result SHALL report a draw and SHALL include the full sequence of columns played

#### Scenario: First mover is configurable
- **WHEN** a match is started with a specified first-moving player
- **THEN** that player SHALL make the first move of the game
