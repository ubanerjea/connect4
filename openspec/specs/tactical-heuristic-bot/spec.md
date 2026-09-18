# tactical-heuristic-bot Specification

## Purpose
A heuristic Connect 4 bot that extends the Phase 9 three-rule priority order with fork-creation (rule 3) and fork-blocking (rule 4), creating stronger challenge pressure by forcing agents to learn defensive multi-step threat recognition.

## Requirements

### Requirement: Tactical heuristic bot extends three-rule priority with fork awareness
The system SHALL provide a `tactical_heuristic_bot` that selects moves using the following five-rule priority order, checking each rule in sequence and moving to the next only if no candidates pass: (1) win immediately; (2) block opponent's 1-ply win; (3) create a fork (give self ≥ 2 simultaneous winning threats after the move); (4) block opponent's fork (deny opponent a move that would give them ≥ 2 simultaneous winning threats); (5) prefer center column (nearest available column to board center).

#### Scenario: Tactical bot wins immediately when possible
- **WHEN** there exists a legal column that completes four-in-a-row for the current player
- **THEN** the tactical bot SHALL select one such column

#### Scenario: Tactical bot blocks opponent's 1-ply win when no immediate win exists
- **WHEN** no immediate win exists for the current player but the opponent can win next move in some column
- **THEN** the tactical bot SHALL select one such blocking column

#### Scenario: Tactical bot creates a fork when no win or 1-ply block applies
- **WHEN** no immediate win or 1-ply block applies, but there exists a column that after being played leaves the current player with two or more winning threat columns (excluding the just-played column)
- **THEN** the tactical bot SHALL select one such fork-creating column

#### Scenario: Tactical bot blocks opponent's fork when no higher-priority rule applies
- **WHEN** no immediate win, 1-ply block, or own-fork creation applies, but there exists a column the opponent could play to give themselves two or more winning threats
- **THEN** the tactical bot SHALL select one such fork-blocking column

#### Scenario: Tactical bot falls back to center preference when no tactical rule applies
- **WHEN** none of the four tactical rules produce a candidate
- **THEN** the tactical bot SHALL select one of the legal columns nearest to the board's center column

### Requirement: Heuristic bot level is configurable
The system SHALL select the active heuristic bot based on the `heuristic_bot_level` configuration parameter. `"basic"` SHALL reproduce the Phase 9 three-rule heuristic bot behavior exactly (identical move choices given identical board state and RNG); `"tactical"` SHALL use the five-rule tactical bot. No other values need be supported.

#### Scenario: basic level selects Phase 9 three-rule bot
- **WHEN** `heuristic_bot_level` is `"basic"`
- **THEN** heuristic challenge games SHALL use the original three-rule heuristic bot, with identical outcomes to an equivalent Phase 9 run

#### Scenario: tactical level selects five-rule tactical bot
- **WHEN** `heuristic_bot_level` is `"tactical"`
- **THEN** heuristic challenge games SHALL use the five-rule tactical bot

### Requirement: Tactical bot signature is identical to the basic heuristic bot
The system SHALL expose `tactical_heuristic_bot` with the same signature as `heuristic_bot` (`board: Board, rng=None → int`), so it can be used as a drop-in replacement without changes to the game framework or match runner.

#### Scenario: Tactical bot is callable in place of basic heuristic bot
- **WHEN** `tactical_heuristic_bot` is called with a Board and an optional RNG
- **THEN** it SHALL return a legal integer column index for the current board state
