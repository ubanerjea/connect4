## ADDED Requirements

### Requirement: Population snapshots can be listed
The system SHALL allow listing all recorded population snapshots, ordered by tick, optionally filtered to a single tick.

#### Scenario: Listing all snapshots returns them in tick order
- **WHEN** multiple population snapshots have been recorded at different ticks
- **THEN** listing all snapshots SHALL return them ordered by tick

#### Scenario: Listing filtered by tick returns only that tick's snapshot
- **WHEN** population snapshots from multiple different ticks exist in storage
- **THEN** listing snapshots for one specific tick SHALL return only the snapshot recorded at that tick
