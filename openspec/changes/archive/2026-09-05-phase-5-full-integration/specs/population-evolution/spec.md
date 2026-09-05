## ADDED Requirements

### Requirement: A population can be reconstructed from storage
The system SHALL be able to reconstruct a fully live, in-progress population entirely from previously stored records — every currently-alive agent (including its lineage, genome, live stats, and parent-average fitness), the current tick, and the random-number-generator continuation state — such that the reconstructed population can continue running ticks indistinguishably from the original in-memory population at the moment it was last persisted.

#### Scenario: All alive agents are restored
- **WHEN** a population with a mix of alive and dead agents is reconstructed from storage
- **THEN** the reconstructed population SHALL contain exactly the agents that were alive, with no dead agents included

#### Scenario: Restored agents preserve genome, lineage, and live stats
- **WHEN** an agent is reconstructed from storage
- **THEN** its genome, parent references, generation, parent-average fitness, and games-played/wins/losses/draws/fitness/games-since-last-reproduction SHALL all match the values it had when last persisted

#### Scenario: Restored population resumes ticking from the correct tick
- **WHEN** a population is reconstructed from storage
- **THEN** running a tick against it SHALL advance from the persisted current tick, not from zero

#### Scenario: Restored population preserves tier-2 cull ordering
- **WHEN** a reconstructed population's population cap is enforced and immature-offspring culling is enabled
- **THEN** immature agents SHALL be ranked for culling by their persisted parent-average fitness, not a value of zero
