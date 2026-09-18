## MODIFIED Requirements

### Requirement: Fitness reflects win rate
The system SHALL recompute each alive agent's overall fitness each tick using a three-track adaptive formula. Peer fitness, heuristic fitness, and Hall of Fame fitness are each computed independently from their respective counter sets, then blended using adaptive weights β_peer, β_h, and β_hof that sum to exactly 1.0. β_h and β_hof are derived each tick from a rolling window of recent heuristic benchmark results (see adaptive weight requirement below). β_peer is fixed at `1.0 − β_h − β_hof`. Peer fitness counts draws as half a win against peer games played; heuristic fitness counts wins (1.0), draws (0.5), and accumulated survival credit against heuristic games played; HoF fitness counts wins (1.0), draws (0.5), and accumulated HoF survival credit against HoF games played. If any counter is zero, that track contributes 0.0 to the blend.

#### Scenario: Fitness matches the three-track adaptive formula
- **WHEN** an agent has known peer, heuristic, and HoF counter values after a tick
- **THEN** its fitness SHALL equal `β_peer × peer_fitness + β_h × heuristic_fitness + β_hof × hof_fitness`, where each track fitness is computed from its counters or 0.0 if games played is zero, and the three β values sum to exactly 1.0

#### Scenario: HoF track contributes zero when HoF is empty
- **WHEN** the Hall of Fame has no active members
- **THEN** β_hof SHALL be 0.0 regardless of the rolling window value, and the formula SHALL degrade to the two-track peer + heuristic formula

#### Scenario: Survival credit accrues on HoF losses
- **WHEN** an alive agent loses a HoF challenge game in N moves on a board with B total cells
- **THEN** the agent's `hof_survival_credit` SHALL increase by `heuristic_survival_alpha × N / B`

## ADDED Requirements

### Requirement: Fitness weights adapt to rolling heuristic benchmark win rate
The system SHALL compute β_h and β_hof each tick by querying the most recent `heuristic_weight_adapt_window` benchmark results of type `'heuristic'`, computing their average win rate as `rolling_wr`, clamping a normalized interpolation parameter `t = clamp((rolling_wr − adapt_low) / (adapt_high − adapt_low), 0, 1)`, then setting `β_h = weight_max − t × (weight_max − weight_min)` and `β_hof = t × hof_weight_max` (zero-clamped when HoF is empty). If no benchmark results exist, `rolling_wr = 0.0` (treat as no mastery proven).

#### Scenario: Low rolling win rate keeps β_h at maximum
- **WHEN** the rolling heuristic win rate is at or below `heuristic_weight_adapt_low`
- **THEN** β_h SHALL equal `heuristic_fitness_weight_max` and β_hof SHALL equal 0.0 (before HoF weight applies)

#### Scenario: High rolling win rate shifts weight toward HoF
- **WHEN** the rolling heuristic win rate is at or above `heuristic_weight_adapt_high`
- **THEN** β_h SHALL equal `heuristic_fitness_weight_min` and β_hof SHALL equal `hof_fitness_weight_max` (if HoF has active members)

#### Scenario: Adaptive weights always sum to 1.0
- **WHEN** β_h and β_hof are computed for any rolling win rate value
- **THEN** β_peer + β_h + β_hof SHALL equal exactly 1.0

#### Scenario: Adaptive weights use ticks 0..N-1 at tick N
- **WHEN** fitness is recomputed at tick N
- **THEN** the rolling window SHALL use benchmark results from ticks before N, not the benchmark result recorded at tick N (which runs after fitness recomputation)

### Requirement: run_tick executes HoF challenge and maintenance phases
The system SHALL, within each tick, execute HoF challenge games after heuristic challenges and before fitness recomputation, and execute HoF maintenance after the benchmark step. The canonical tick ordering SHALL be: peer games → heuristic challenges → HoF challenges → fitness recomputation → reproduction/death/culling → benchmark → HoF maintenance → snapshot → commit.

#### Scenario: HoF challenge phase runs before fitness recomputation each tick
- **WHEN** a tick runs with active HoF members
- **THEN** HoF challenge games SHALL complete and HoF counters SHALL be updated before `_recompute_fitness()` is called

#### Scenario: HoF maintenance runs after benchmark each tick
- **WHEN** a tick is a maintenance tick
- **THEN** HoF maintenance SHALL run after the benchmark step so the latest benchmark result is committed before candidate evaluation

### Requirement: A population reconstructed from storage restores HoF agent counters
The system SHALL, when reconstructing a population from storage, restore every alive agent's four HoF counters (`hof_wins`, `hof_draws`, `hof_games_played`, `hof_survival_credit`) to the values they had when last persisted, so three-track fitness computation produces correct results in the resumed run.

#### Scenario: Restored agents preserve HoF counters
- **WHEN** a population containing agents with non-zero HoF counter values is reconstructed from storage
- **THEN** every restored agent's HoF counters SHALL match the values that were last persisted
