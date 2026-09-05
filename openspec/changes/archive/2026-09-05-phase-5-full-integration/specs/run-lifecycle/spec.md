## Purpose

Governs how a headless simulation run is invoked from the command line: how long it runs, whether it starts a fresh population or resumes an existing one, and how reproducibly it does either.

## ADDED Requirements

### Requirement: CLI accepts ticks, seed, and database path arguments
The system SHALL accept `--ticks` (number of ticks to run this invocation, default 500), `--seed` (RNG seed override), and `--db` (target database file path, default an auto-generated timestamped path) as command-line arguments to the simulation entry point.

#### Scenario: Default invocation runs the default tick count
- **WHEN** the entry point is invoked with no arguments
- **THEN** it SHALL run 500 ticks against an auto-generated timestamped database path

#### Scenario: Explicit ticks argument is honored
- **WHEN** the entry point is invoked with `--ticks 50`
- **THEN** it SHALL run exactly 50 ticks

### Requirement: Target database path determines fresh start vs. resume
The system SHALL start a fresh population when the target `--db` path does not exist or contains no live population, and SHALL resume the existing population when the target path already contains one.

#### Scenario: Nonexistent path starts fresh
- **WHEN** `--db` names a path with no existing file
- **THEN** the system SHALL initialize a brand-new population at that path

#### Scenario: Existing path with a live population resumes
- **WHEN** `--db` names a path whose database already contains at least one alive agent
- **THEN** the system SHALL resume that population instead of creating a new one

### Requirement: Seed selection differs between a fresh start and a resume
The system SHALL determine the run's random seed according to whether it is a fresh start or a resume: on a fresh start, `--seed` if given, else the configured `random_seed`; on a resume, the exact persisted RNG state if `--seed` is not given, or a newly seeded generator if `--seed` is given.

#### Scenario: Fresh start uses the seed override when given
- **WHEN** a fresh start is invoked with `--seed 7`
- **THEN** the new population's RNG SHALL be seeded with 7

#### Scenario: Fresh start falls back to configured seed
- **WHEN** a fresh start is invoked with no `--seed`
- **THEN** the new population's RNG SHALL be seeded with the configured `random_seed`

#### Scenario: Resume with no seed override continues identically
- **WHEN** a run is stopped after some ticks and resumed with no `--seed` argument
- **THEN** the resumed run's tick-by-tick outcomes SHALL be identical to what an uninterrupted run with the same original seed would have produced from that point forward

#### Scenario: Resume with a seed override branches deliberately
- **WHEN** a resume is invoked with `--seed` given
- **THEN** the system SHALL continue from the persisted population state but generate all further randomness from a newly seeded generator instead of the old RNG stream

### Requirement: Resume validates frozen configuration before proceeding
The system SHALL compare every frozen configuration field in the live configuration against the value recorded for that population when it was created, and SHALL refuse to resume — making no changes to the database — if any frozen field differs, naming every mismatched field in the error.

#### Scenario: Matching frozen config resumes normally
- **WHEN** a resume's live configuration matches the recorded frozen configuration in every frozen field
- **THEN** the resume SHALL proceed

#### Scenario: Mismatched frozen config refuses the resume
- **WHEN** a resume's live configuration differs from the recorded frozen configuration in at least one frozen field
- **THEN** the system SHALL refuse to resume, name every mismatched field in the error, and leave the target database unchanged
