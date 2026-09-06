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
    assert {
        "agents",
        "games",
        "population_snapshots",
        "benchmark_results",
        "simulation_config",
        "simulation_config_history",
        "simulation_state",
    } <= tables


def test_agents_table_has_parent_avg_fitness_column():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
    assert "parent_avg_fitness" in cols


def test_simulation_config_rejects_a_second_row():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute(
        "INSERT INTO simulation_config (id, simulation_id, board_columns, board_rows, "
        "hidden_layer_sizes, weight_init_std) VALUES (1, 'a', 7, 6, '[24]', 0.5)"
    )
    try:
        conn.execute(
            "INSERT INTO simulation_config (id, simulation_id, board_columns, board_rows, "
            "hidden_layer_sizes, weight_init_std) VALUES (1, 'b', 7, 6, '[24]', 0.5)"
        )
        assert False, "expected a second insert to be rejected"
    except sqlite3.IntegrityError:
        pass


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
        "idx_games_game_type",
    }
    assert expected <= indices


def test_games_table_agent_ids_are_nullable_and_has_opponent_label():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    cols = {row[1]: row[3] for row in conn.execute("PRAGMA table_info(games)").fetchall()}
    assert cols["player1_agent_id"] == 0  # notnull flag off
    assert cols["player2_agent_id"] == 0
    assert "opponent_label" in cols


def test_create_schema_is_idempotent():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    create_schema(conn)  # should not raise
    assert {"agents", "games", "population_snapshots", "benchmark_results"} <= _table_names(conn)
