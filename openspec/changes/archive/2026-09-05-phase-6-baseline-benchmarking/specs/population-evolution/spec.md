## ADDED Requirements

### Requirement: The current-best agent is periodically benchmarked against fixed opponents
The system SHALL, every `benchmark_every_n_ticks`, have the current-best-by-fitness alive agent (determined after that tick's reproduction, death, and culling) play `benchmark_games_per_opponent` games against each of a set of fixed baseline opponents, alternating which side moves first, record a benchmark result per opponent, and record the individual games durably — without altering the benchmarked agent's own official games-played, win, loss, draw, or fitness counters.

#### Scenario: Benchmark evaluation happens on schedule
- **WHEN** a tick's number is a multiple of `benchmark_every_n_ticks` and the population is not empty
- **THEN** the current-best-by-fitness alive agent SHALL play `benchmark_games_per_opponent` games against each fixed baseline opponent that tick

#### Scenario: Off-schedule ticks are not benchmarked
- **WHEN** a tick's number is not a multiple of `benchmark_every_n_ticks`
- **THEN** no benchmark evaluation SHALL occur that tick

#### Scenario: Benchmark games do not affect the agent's official record
- **WHEN** the current-best agent plays its scheduled benchmark games
- **THEN** its games-played, wins, losses, draws, and fitness SHALL be unchanged by those games

#### Scenario: A benchmark result is recorded per opponent
- **WHEN** a benchmark evaluation completes against one fixed opponent
- **THEN** a benchmark result SHALL be recorded reflecting that opponent's win rate over the games played
