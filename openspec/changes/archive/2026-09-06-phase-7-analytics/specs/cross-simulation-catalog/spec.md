## Purpose

Rolls up aggregate-only data from many independent simulation-run databases into one shared, queryable database, so runs can be compared by their configuration and outcome trends without manually attaching files.

## ADDED Requirements

### Requirement: Catalog rolls up multiple run databases into one shared database
The system SHALL scan a directory of run databases and record, for each one that has a simulation identifier, a summary row in a shared catalog database combining that run's frozen configuration, its initial mutable configuration, and its aggregate-level population-snapshot and benchmark-result history.

#### Scenario: Scanning a directory with multiple runs produces one row per run
- **WHEN** the catalog step scans a directory containing two or more run databases
- **THEN** the shared catalog database's summary table SHALL contain exactly one row per run

#### Scenario: A run database without a simulation identifier is skipped
- **WHEN** a database in the scanned directory has no simulation identifier recorded
- **THEN** the catalog step SHALL skip that database without error

### Requirement: The catalog stores aggregate data only
The system SHALL copy only already-aggregated data (population snapshots and benchmark results, plus per-run configuration) into the catalog, and SHALL NOT copy individual agent or game records.

#### Scenario: Cataloging a run does not copy per-agent or per-game detail
- **WHEN** a run is cataloged
- **THEN** no individual agent or game record from that run SHALL appear in the catalog database

### Requirement: Cataloging is idempotent
The system SHALL make re-running the catalog step against unchanged run databases produce no additional or duplicate rows, and SHALL, when a previously-cataloged run has advanced further, add only the data recorded since it was last cataloged.

#### Scenario: Re-cataloging an unchanged set of runs is a no-op
- **WHEN** the catalog step is run twice against the same, unchanged set of run databases
- **THEN** the second run SHALL make no changes to the catalog database

#### Scenario: Re-cataloging an advanced run picks up only new data
- **WHEN** a previously-cataloged run has recorded further ticks since it was last cataloged, and the catalog step is run again
- **THEN** only the data recorded since the last cataloging SHALL be added, and no previously-cataloged data SHALL be duplicated or altered
