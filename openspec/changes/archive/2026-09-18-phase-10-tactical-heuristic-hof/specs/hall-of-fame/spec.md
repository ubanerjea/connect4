## Purpose

Maintains a persisted pool of the population's past-best agents (Hall of Fame), periodically evaluated for quality and rotated by entry/eviction rules, used as a standing challenge opponent for all alive agents each tick to create selection pressure toward both offense and defense.

## ADDED Requirements

### Requirement: Hall of Fame table is created in storage
The system SHALL create a `hall_of_fame` table if it does not already exist, with columns for member id, referenced agent id, induction tick, eviction tick, status, heuristic win rate, internal (intra-HoF) score, and combined score. The table SHALL be addable to an existing database via a migration that does not alter existing data.

#### Scenario: Fresh database contains the hall_of_fame table
- **WHEN** the storage layer is initialized against a fresh database
- **THEN** the `hall_of_fame` table SHALL exist with all required columns and default values

#### Scenario: Existing Phase 9 database gains the table via migration
- **WHEN** the storage layer is initialized against a database that lacks the `hall_of_fame` table
- **THEN** the table SHALL be created without altering any existing rows

### Requirement: HoF members reference agents by id without duplicating genome data
The system SHALL store HoF members as references to `agents.agent_id`. The genome stored in `agents.nn_weights` SHALL remain loadable indefinitely; the HoF record SHALL NOT store a second copy of the genome.

#### Scenario: Inducted agent's genome is recoverable from agents table
- **WHEN** an agent is inducted into the Hall of Fame
- **THEN** its genome SHALL be recoverable by reading `nn_weights` from the `agents` table using the stored `agent_id` reference

### Requirement: Active HoF members serve as per-tick challenge opponents
The system SHALL, each tick after heuristic challenge games and before fitness recomputation, have every alive agent play `hof_games_per_agent_per_tick` games against randomly-sampled active HoF members (sampling with replacement if HoF size < games per agent). If the HoF has no active members this step SHALL be skipped entirely. These games SHALL count toward the living agent's `games_played` and `games_since_last_reproduction`.

#### Scenario: Each alive agent plays the configured number of HoF games per tick
- **WHEN** a tick runs with active HoF members and `hof_games_per_agent_per_tick = N`
- **THEN** every alive agent SHALL play exactly N games against randomly-sampled active HoF members that tick

#### Scenario: Per-tick HoF challenge games count toward games_played
- **WHEN** an alive agent plays a HoF challenge game
- **THEN** both its `games_played` and `games_since_last_reproduction` SHALL increase by one

#### Scenario: Empty HoF skips per-tick challenges
- **WHEN** a tick runs and the HoF has no active members
- **THEN** no HoF challenge games SHALL be generated and no HoF counters SHALL change

#### Scenario: HoF challenges are recorded as hof_challenge game type
- **WHEN** a per-tick HoF challenge game is logged
- **THEN** it SHALL carry `game_type = 'hof_challenge'`, the living agent's id in the first player slot, the HoF member's `agent_id` in the second player slot, and no `opponent_label`

### Requirement: HoF agent counters track HoF challenge performance
The system SHALL maintain four counters on alive agents for HoF challenge results: `hof_wins`, `hof_draws`, `hof_games_played`, and `hof_survival_credit`. Survival credit accumulates on HoF losses at the same rate as heuristic survival credit (`heuristic_survival_alpha × num_moves / (board_columns × board_rows)`). These counters SHALL default to zero on agent creation and be included in every agent update operation.

#### Scenario: Win in HoF challenge increments hof_wins and hof_games_played
- **WHEN** a living agent wins a HoF challenge game
- **THEN** its `hof_wins` and `hof_games_played` SHALL each increase by one

#### Scenario: Loss in HoF challenge accrues survival credit
- **WHEN** a living agent loses a HoF challenge game in N moves on a board with B total cells
- **THEN** its `hof_survival_credit` SHALL increase by `heuristic_survival_alpha × N / B`

#### Scenario: New agent has zero HoF counters
- **WHEN** an agent record is inserted (initial population or reproduction)
- **THEN** all four HoF counters SHALL be zero

### Requirement: HoF maintenance runs on a configured tick interval
The system SHALL run a unified HoF entry and eviction maintenance event on every tick where `tick mod hof_maintenance_every_n_ticks == 0`. This event SHALL: (1) re-evaluate each active member's heuristic win rate vs. the current heuristic bot; (2) run intra-HoF pairing games and compute each member's internal score and combined score; (3) evaluate the current best-alive-by-fitness candidate for induction; (4) induct the candidate if eligible and the hall has room, or induct and evict the weakest member if the hall is full and the candidate clears the eviction margin.

#### Scenario: Maintenance runs only on scheduled ticks
- **WHEN** a tick is not a multiple of `hof_maintenance_every_n_ticks`
- **THEN** no maintenance SHALL run, no hall_of_fame rows SHALL change, and no maintenance games SHALL be logged

#### Scenario: Member heuristic win rate is updated at maintenance
- **WHEN** HoF maintenance runs
- **THEN** each active member SHALL play `hof_maintenance_heuristic_games` games vs. the heuristic bot and its `heuristic_win_rate` in the `hall_of_fame` table SHALL be updated to reflect that series

#### Scenario: Intra-HoF games update internal_score and combined_score
- **WHEN** HoF maintenance runs with at least two active members
- **THEN** each member SHALL play `hof_maintenance_peer_games` per matched pair, and each member's `internal_score` and `combined_score` (0.5 × heuristic_win_rate + 0.5 × internal_score) SHALL be updated

#### Scenario: Candidate meeting entry threshold is inducted when hall has room
- **WHEN** HoF maintenance runs and the best-alive-by-fitness agent's heuristic win rate against the current bot is at least `hof_entry_heuristic_threshold` and the active HoF count is less than `hof_max_size`
- **THEN** that agent SHALL be inducted with its evaluated heuristic win rate recorded and status set to `'active'`

#### Scenario: Candidate below entry threshold is not inducted
- **WHEN** HoF maintenance runs and the candidate's heuristic win rate is below `hof_entry_heuristic_threshold`
- **THEN** no induction SHALL occur regardless of HoF size

#### Scenario: Full hall inducts candidate and evicts weakest when eviction margin is met
- **WHEN** HoF maintenance runs, the hall is at `hof_max_size`, and the candidate's heuristic win rate exceeds the weakest member's `heuristic_win_rate` by at least `hof_eviction_margin`
- **THEN** the weakest member SHALL be evicted (status set to `'evicted'`, `evicted_tick` recorded) and the candidate SHALL be inducted

#### Scenario: Full hall unchanged when eviction margin is not met
- **WHEN** HoF maintenance runs, the hall is at `hof_max_size`, and the candidate's heuristic win rate does NOT exceed the weakest member's by the eviction margin
- **THEN** neither eviction nor induction SHALL occur that cycle

#### Scenario: Maintenance games do not affect living agent counters
- **WHEN** HoF maintenance games (member vs. heuristic or intra-HoF peer games) are played
- **THEN** no living agent's `games_played`, `games_since_last_reproduction`, `wins`, `losses`, or `draws` SHALL change as a result

#### Scenario: Candidate evaluation does not alter the candidate's counters
- **WHEN** the candidate is evaluated against the heuristic bot during maintenance
- **THEN** the candidate's `games_played`, `games_since_last_reproduction`, and all fitness counters SHALL remain unchanged

#### Scenario: Already-active agent is not inducted twice
- **WHEN** HoF maintenance runs and the best-alive agent is already an active HoF member
- **THEN** no duplicate induction record SHALL be created

### Requirement: HoF maintenance games are logged as distinct game types
The system SHALL log maintenance games with `game_type = 'hof_maintenance_heuristic'` (member vs. heuristic bot) or `game_type = 'hof_maintenance_peer'` (intra-HoF pair games) for analytics and auditability.

#### Scenario: Member-vs-heuristic maintenance game is logged correctly
- **WHEN** a HoF member plays the heuristic bot during maintenance
- **THEN** the game record SHALL carry `game_type = 'hof_maintenance_heuristic'`, the member's `agent_id` as player1, no player2 agent id, and `opponent_label = 'heuristic'`

#### Scenario: Intra-HoF pair game is logged correctly
- **WHEN** two HoF members play each other during maintenance
- **THEN** the game record SHALL carry `game_type = 'hof_maintenance_peer'`, both members' `agent_id` values in the player slots, and no `opponent_label`

### Requirement: HoF is disabled when hof_enabled is false
The system SHALL, when `hof_enabled` is false, skip all HoF logic — per-tick challenges, maintenance, and fitness contribution — producing no HoF games and leaving β_hof at 0.0.

#### Scenario: Disabling HoF produces no HoF games
- **WHEN** `hof_enabled` is false and a tick runs
- **THEN** no `hof_challenge`, `hof_maintenance_heuristic`, or `hof_maintenance_peer` games SHALL be logged and β_hof SHALL be 0.0

### Requirement: Population load restores HoF state
The system SHALL, when reconstructing a population from storage, restore all four HoF counters for every alive agent and reconstruct active HoF members as Agent objects (loading genomes from `agents.nn_weights`) ready for per-tick challenge sampling.

#### Scenario: Restored alive agents have correct HoF counters
- **WHEN** a population with non-zero HoF counters is reconstructed from storage
- **THEN** every restored agent's `hof_wins`, `hof_draws`, `hof_games_played`, and `hof_survival_credit` SHALL match the values last persisted

#### Scenario: Active HoF members are ready for per-tick challenge sampling after load
- **WHEN** a population is reconstructed from storage and the first tick runs
- **THEN** active HoF members SHALL be available as opponents for HoF challenge games without requiring a maintenance cycle to run first
