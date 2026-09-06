"""SQLite table definitions (plan Sec6)."""

from __future__ import annotations

import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id INTEGER PRIMARY KEY,
    parent1_id INTEGER REFERENCES agents(agent_id),
    parent2_id INTEGER REFERENCES agents(agent_id),
    generation INTEGER NOT NULL,
    birth_tick INTEGER NOT NULL,
    death_tick INTEGER,
    status TEXT NOT NULL,
    death_cause TEXT,
    nn_weights TEXT NOT NULL,
    nn_architecture TEXT NOT NULL,
    lifespan INTEGER NOT NULL,
    mutation_rate REAL NOT NULL,
    crossover_rate REAL NOT NULL,
    games_played INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    draws INTEGER NOT NULL,
    fitness REAL NOT NULL,
    games_since_last_reproduction INTEGER NOT NULL,
    offspring_count INTEGER NOT NULL,
    parent_avg_fitness REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY,
    tick INTEGER NOT NULL,
    player1_agent_id INTEGER REFERENCES agents(agent_id),
    player2_agent_id INTEGER REFERENCES agents(agent_id),
    result TEXT NOT NULL,
    num_moves INTEGER NOT NULL,
    move_history TEXT NOT NULL,
    game_type TEXT NOT NULL,
    opponent_label TEXT
);

CREATE TABLE IF NOT EXISTS population_snapshots (
    snapshot_id INTEGER PRIMARY KEY,
    tick INTEGER NOT NULL,
    population_size INTEGER NOT NULL,
    avg_fitness REAL NOT NULL,
    max_fitness REAL NOT NULL,
    min_fitness REAL NOT NULL,
    avg_lifespan REAL NOT NULL,
    avg_mutation_rate REAL NOT NULL,
    best_agent_id INTEGER REFERENCES agents(agent_id)
);

CREATE TABLE IF NOT EXISTS benchmark_results (
    benchmark_id INTEGER PRIMARY KEY,
    tick INTEGER NOT NULL,
    agent_id INTEGER NOT NULL REFERENCES agents(agent_id),
    opponent_type TEXT NOT NULL,
    games_played INTEGER NOT NULL,
    win_rate REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    simulation_id TEXT NOT NULL,
    board_columns INTEGER NOT NULL,
    board_rows INTEGER NOT NULL,
    hidden_layer_sizes TEXT NOT NULL,
    weight_init_std REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_config_history (
    history_id INTEGER PRIMARY KEY,
    tick INTEGER NOT NULL,
    population_size INTEGER NOT NULL,
    lifespan_range TEXT NOT NULL,
    lifespan_mutation_scale REAL NOT NULL,
    mutation_rate_range TEXT NOT NULL,
    mutation_rate_tau REAL NOT NULL,
    crossover_rate_range TEXT NOT NULL,
    crossover_rate_mutation_std REAL NOT NULL,
    tournament_size INTEGER NOT NULL,
    reproduction_interval_min INTEGER NOT NULL,
    reproduction_interval_max INTEGER NOT NULL,
    games_per_pair_per_tick INTEGER NOT NULL,
    benchmark_every_n_ticks INTEGER NOT NULL,
    benchmark_games_per_opponent INTEGER NOT NULL,
    random_seed INTEGER NOT NULL,
    cull_fraction_range TEXT NOT NULL,
    cull_fraction_beta_a REAL NOT NULL,
    cull_fraction_beta_b REAL NOT NULL,
    cull_allow_immature_offspring INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_tick INTEGER NOT NULL,
    rng_state TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_parent1_id ON agents(parent1_id);
CREATE INDEX IF NOT EXISTS idx_agents_parent2_id ON agents(parent2_id);
CREATE INDEX IF NOT EXISTS idx_games_tick ON games(tick);
CREATE INDEX IF NOT EXISTS idx_games_player1_agent_id ON games(player1_agent_id);
CREATE INDEX IF NOT EXISTS idx_games_player2_agent_id ON games(player2_agent_id);
CREATE INDEX IF NOT EXISTS idx_games_game_type ON games(game_type);
CREATE INDEX IF NOT EXISTS idx_simulation_config_history_tick ON simulation_config_history(tick);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
