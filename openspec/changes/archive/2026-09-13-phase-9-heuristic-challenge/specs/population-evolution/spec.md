## MODIFIED Requirements

### Requirement: Fitness reflects win rate
The system SHALL recompute each alive agent's overall fitness each tick using a two-track formula: peer fitness and heuristic fitness are each computed independently from their respective counter sets and blended using a configured weight β (`heuristic_fitness_weight`). Peer fitness counts draws as half a win against peer games played; heuristic fitness counts wins (1.0), draws (0.5), and accumulated survival credit (proportional to game length on losses) against heuristic games played. If either counter is zero, that track contributes 0.0 to the blend. The resulting overall fitness is bounded to `[0, 1]` by the formula's construction when all inputs are non-negative.

#### Scenario: Fitness matches the two-track formula
- **WHEN** an agent has known peer and heuristic counter values after a tick
- **THEN** its fitness SHALL equal `(1 − β) × peer_fitness + β × heuristic_fitness`, where `peer_fitness = (peer_wins + 0.5 × peer_draws) / peer_games_played` (or 0.0 if `peer_games_played = 0`) and `heuristic_fitness = (heuristic_wins + 0.5 × heuristic_draws + heuristic_survival_credit) / heuristic_games_played` (or 0.0 if `heuristic_games_played = 0`)

#### Scenario: Survival credit accrues only on heuristic losses
- **WHEN** a heuristic challenge game ends in a loss for the agent
- **THEN** the agent's `heuristic_survival_credit` SHALL increase by `α × num_moves / (board_columns × board_rows)`, and SHALL remain unchanged when the game ends in a win or draw

#### Scenario: Zero heuristic games degrades to peer-only fitness
- **WHEN** `heuristic_games_per_agent_per_tick` is 0 and an agent has played only peer games
- **THEN** its fitness SHALL equal `(1 − β) × peer_fitness`, with the heuristic track contributing 0.0

## ADDED Requirements

### Requirement: Every alive agent plays heuristic challenge games each tick
The system SHALL, after pairing games complete and before fitness is recomputed, have every currently-alive agent play exactly `heuristic_games_per_agent_per_tick` games against the heuristic bot, alternating which side moves first by game index, and SHALL update that agent's heuristic-track counters (`heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`), unified counters (`wins`, `losses`, `draws`, `games_played`, `games_since_last_reproduction`), and store each game durably. If `heuristic_games_per_agent_per_tick` is 0 the system SHALL skip this step entirely, producing no games and leaving all counters unchanged.

#### Scenario: Each alive agent plays the configured number of heuristic games
- **WHEN** a tick runs with `heuristic_games_per_agent_per_tick = N > 0` and M alive agents
- **THEN** exactly M × N heuristic challenge games SHALL be played and durably stored that tick, and every alive agent's `heuristic_games_played` SHALL increase by N

#### Scenario: Heuristic challenge games count toward `games_since_last_reproduction` and `games_played`
- **WHEN** an agent plays a heuristic challenge game
- **THEN** both its `games_since_last_reproduction` and its unified `games_played` SHALL increase by one, so heuristic games advance the reproduction and lifespan countdowns identically to peer games

#### Scenario: Disabling heuristic challenges restores Phase 8 behavior
- **WHEN** `heuristic_games_per_agent_per_tick` is 0
- **THEN** no heuristic challenge games SHALL be generated that tick, no heuristic-track counters SHALL change, the RNG state at tick end SHALL be identical to what it would be in a Phase 8 run with the same peer games, and overall fitness SHALL degrade cleanly to the peer-only signal

#### Scenario: Heuristic challenge games are recorded as a distinct game type
- **WHEN** heuristic challenge games are logged
- **THEN** they SHALL carry `game_type = 'evolution_heuristic'`, the agent's id in the first player slot, no second agent id, and `opponent_label = 'heuristic'`

#### Scenario: Heuristic challenge games do not affect the agent's benchmark or official evolution record
- **WHEN** the benchmarking step runs after heuristic challenges in the same tick
- **THEN** the benchmarked agent's `games_played`, `wins`, `losses`, `draws`, and `fitness` values SHALL reflect the heuristic challenge games that tick, but the benchmark result itself SHALL still not alter those counters further

### Requirement: A population reconstructed from storage restores heuristic-track counters
The system SHALL, when reconstructing a population from storage, restore every alive agent's heuristic-track counters (`peer_wins`, `peer_draws`, `peer_games_played`, `heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`) to the values they had when last persisted, so that two-track fitness computation produces identical results from the resumed population.

#### Scenario: Restored agents preserve heuristic-track counters
- **WHEN** a population containing agents with non-zero heuristic-track counter values is reconstructed from storage
- **THEN** every restored agent's heuristic-track counters SHALL match the values that were last persisted

#### Scenario: Resumed run reproduces tick-by-tick fitness values
- **WHEN** a run is paused after a tick and resumed, with heuristic challenges enabled
- **THEN** the fitness values computed in the first resumed tick SHALL be identical to those that would have been computed had the run not been paused
