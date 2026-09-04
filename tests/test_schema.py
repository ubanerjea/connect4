import sqlite3

from evoconnect4.storage.schema import create_schema


def _table_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def _index_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return {row[0] for row in rows}


def test_create_schema_creates_all_tables():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    tables = _table_names(conn)
    assert {"agents", "games", "population_snapshots", "benchmark_results"} <= tables


def test_create_schema_creates_all_indices():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    indices = _index_names(conn)
    expected = {
        "idx_agents_status",
        "idx_agents_parent1_id",
        "idx_agents_parent2_id",
        "idx_games_tick",
        "idx_games_player1_agent_id",
        "idx_games_player2_agent_id",
    }
    assert expected <= indices


def test_create_schema_is_idempotent():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    create_schema(conn)  # should not raise
    assert {"agents", "games", "population_snapshots", "benchmark_results"} <= _table_names(conn)
