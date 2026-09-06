## Purpose

Generates chart images from a single simulation run's database, so trends in population fitness, benchmark performance, population size, and gene drift can be inspected visually after (or during) a run.

## ADDED Requirements

### Requirement: Chart generation from a single run's database
The system SHALL generate four chart images — population fitness over time, benchmark win-rate over time, population size over time, and gene drift over time — from a run's database, writing each as an image file to a specified output directory.

#### Scenario: Running chart generation against a run's database produces four image files
- **WHEN** chart generation is run against a run's database and an output directory
- **THEN** four image files SHALL be written to that output directory, one per chart

#### Scenario: Output directory is created if missing
- **WHEN** the specified output directory does not already exist
- **THEN** it SHALL be created before any chart is written

### Requirement: Noisy charts include a smoothed trend line
The system SHALL overlay a rolling-average trend line on the raw series for the population-fitness and benchmark-win-rate charts, in addition to the raw (unsmoothed) series.

#### Scenario: Fitness chart shows both raw and smoothed series
- **WHEN** the population-fitness chart is generated
- **THEN** it SHALL include both the raw per-tick series and a rolling-average trend line

### Requirement: Chart data is available independent of rendering
The system SHALL expose each chart's underlying data as a value that can be inspected without rendering an image, so the data's correctness can be verified independently of the chart's visual output.

#### Scenario: Chart data matches the stored records it summarizes
- **WHEN** a chart's underlying data is requested for a run's database
- **THEN** it SHALL reflect exactly the values stored in that run's database for the relevant ticks
