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
    offspring_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY,
    tick INTEGER NOT NULL,
    player1_agent_id INTEGER NOT NULL REFERENCES agents(agent_id),
    player2_agent_id INTEGER NOT NULL REFERENCES agents(agent_id),
    result TEXT NOT NULL,
    num_moves INTEGER NOT NULL,
    move_history TEXT NOT NULL,
    game_type TEXT NOT NULL
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

CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_parent1_id ON agents(parent1_id);
CREATE INDEX IF NOT EXISTS idx_agents_parent2_id ON agents(parent2_id);
CREATE INDEX IF NOT EXISTS idx_games_tick ON games(tick);
CREATE INDEX IF NOT EXISTS idx_games_player1_agent_id ON games(player1_agent_id);
CREATE INDEX IF NOT EXISTS idx_games_player2_agent_id ON games(player2_agent_id);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
