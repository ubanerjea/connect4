## Purpose

Lets a neural-network genome be randomly created, serialized and restored, mutated, and combined with another genome via crossover, and realized into an agent that chooses legal Connect Four moves.

## ADDED Requirements

### Requirement: Network forward pass
The system SHALL compute one score per column from a given board-position input, using a network built from a genome's weights.

#### Scenario: Forward pass produces one score per column
- **WHEN** a network is built from a genome and given a valid board-position input
- **THEN** it SHALL produce exactly one numeric score for each column on the board

### Requirement: Network weights round-trip faithfully
The system SHALL reconstruct a network's full weight vector, given a network built from a genome, identical to the genome's original weight vector.

#### Scenario: Round trip preserves weights exactly
- **WHEN** a network is built from a genome's weight vector and then its weights are extracted back out
- **THEN** the extracted weight vector SHALL be identical to the genome's original weight vector

### Requirement: Random genome initialization
The system SHALL produce a randomly initialized genome whose weight count matches the configured network architecture and whose trait genes fall within their configured bounds.

#### Scenario: Random genome has the correct weight count
- **WHEN** a genome is randomly initialized for a configured network architecture
- **THEN** its weight vector SHALL contain exactly the number of weights and biases that architecture requires

#### Scenario: Random genome's trait genes are within configured bounds
- **WHEN** a genome is randomly initialized
- **THEN** its lifespan SHALL fall within the configured lifespan range, its mutation rate SHALL fall within the configured mutation-rate range, and its crossover rate SHALL fall within the configured crossover-rate range

### Requirement: Genome encode/decode round-trips
The system SHALL restore a genome to an equivalent state after encoding it to a serializable form and decoding it back.

#### Scenario: Decoding an encoded genome reproduces the original
- **WHEN** a genome is encoded to a serializable form and then decoded back
- **THEN** the decoded genome SHALL have the same weight vector, architecture, lifespan, mutation rate, and crossover rate as the original

### Requirement: Mutation produces a new genome without altering the parent
The system SHALL produce a new, mutated genome from a parent genome without modifying the parent.

#### Scenario: Mutation leaves the parent genome unchanged
- **WHEN** a genome is mutated
- **THEN** the original genome's weight vector and trait genes SHALL remain unchanged, and a new genome SHALL be returned

#### Scenario: Mutated trait genes stay within configured bounds
- **WHEN** a genome is mutated
- **THEN** the resulting genome's lifespan, mutation rate, and crossover rate SHALL each remain within their configured bounds

### Requirement: Crossover combines two parent genomes
The system SHALL produce a child genome from two parent genomes, with each weight inherited from one parent or the other, and trait genes averaged.

#### Scenario: Child weights come from one parent or the other
- **WHEN** two genomes are combined via crossover
- **THEN** each weight in the resulting genome SHALL equal the corresponding weight from one of the two parents

#### Scenario: Child trait genes are the average of both parents
- **WHEN** two genomes are combined via crossover
- **THEN** the resulting genome's lifespan, mutation rate, and crossover rate SHALL each equal the average of the two parents' corresponding values

### Requirement: Agent always chooses a legal move
The system SHALL provide a move-choosing agent, built from a genome, that always selects a column that is currently legal on the given board.

#### Scenario: Agent's choice is always legal
- **WHEN** an agent built from a genome is asked to choose a move on a board with at least one legal column
- **THEN** it SHALL return a column that is among the currently legal moves

### Requirement: Move choice is independent of player identity
The system SHALL make an agent's move choice depend only on the arrangement of its own pieces versus its opponent's, not on whether it is playing as the first or second player.

#### Scenario: Consistent choice across player identities
- **WHEN** the same agent is placed in two otherwise-identical positions that differ only in which player identity (first or second) it is playing
- **THEN** it SHALL choose the same column in both cases
