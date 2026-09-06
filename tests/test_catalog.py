import dataclasses
import sqlite3

from evoconnect4.analytics.catalog import (
    catalog_file,
    create_analytics_schema,
    open_analytics_db,
    run_catalog,
)
from evoconnect4.config import load_config
from evoconnect4.run_simulation import run

BASE_CONFIG = load_config()


def _test_config(**overrides):
    return dataclasses.replace(BASE_CONFIG, **overrides)


# -- 1.1 analytics.db schema ---------------------------------------------------


def test_create_analytics_schema_creates_all_tables():
    conn = sqlite3.connect(":memory:")
    create_analytics_schema(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"simulations", "simulation_population_snapshots", "simulation_benchmark_results"} <= tables


def test_simulation_population_snapshots_rejects_duplicate_tick():
    conn = sqlite3.connect(":memory:")
    create_analytics_schema(conn)
    conn.execute(
        "INSERT INTO simulation_population_snapshots "
        "(simulation_id, tick, population_size, avg_fitness, max_fitness, min_fitness, "
        "avg_lifespan, avg_mutation_rate) VALUES ('a', 1, 10, 0.5, 0.9, 0.1, 100.0, 0.2)"
    )
    try:
        conn.execute(
            "INSERT INTO simulation_population_snapshots "
            "(simulation_id, tick, population_size, avg_fitness, max_fitness, min_fitness, "
            "avg_lifespan, avg_mutation_rate) VALUES ('a', 1, 10, 0.6, 0.9, 0.1, 100.0, 0.2)"
        )
        assert False, "expected a duplicate (simulation_id, tick) to be rejected"
    except sqlite3.IntegrityError:
        pass


def test_simulation_benchmark_results_rejects_duplicate_tick_and_opponent():
    conn = sqlite3.connect(":memory:")
    create_analytics_schema(conn)
    conn.execute(
        "INSERT INTO simulation_benchmark_results "
        "(simulation_id, tick, opponent_type, games_played, win_rate) VALUES ('a', 1, 'random', 20, 0.5)"
    )
    try:
        conn.execute(
            "INSERT INTO simulation_benchmark_results "
            "(simulation_id, tick, opponent_type, games_played, win_rate) VALUES ('a', 1, 'random', 20, 0.6)"
        )
        assert False, "expected a duplicate (simulation_id, tick, opponent_type) to be rejected"
    except sqlite3.IntegrityError:
        pass


# -- 1.2 per-file cataloging -----------------------------------------------------


def test_catalog_file_produces_expected_rows(tmp_path):
    db_path = tmp_path / "run.db"
    config = _test_config(population_size=6, benchmark_every_n_ticks=2, benchmark_games_per_opponent=3)
    run(ticks=4, seed=1, db_path=str(db_path), config=config)

    analytics_conn = open_analytics_db(str(tmp_path / "analytics.db"))
    cataloged = catalog_file(analytics_conn, db_path)

    assert cataloged is True
    sim_rows = analytics_conn.execute("SELECT * FROM simulations").fetchall()
    assert len(sim_rows) == 1
    sim_row = dict(sim_rows[0])
    assert sim_row["last_cataloged_tick"] == 4
    assert sim_row["population_size"] == 6
    assert sim_row["source_db_path"] == str(db_path)

    snapshot_count = analytics_conn.execute(
        "SELECT COUNT(*) FROM simulation_population_snapshots WHERE simulation_id = ?",
        (sim_row["simulation_id"],),
    ).fetchone()[0]
    assert snapshot_count == 4  # one per tick

    benchmark_count = analytics_conn.execute(
        "SELECT COUNT(*) FROM simulation_benchmark_results WHERE simulation_id = ?",
        (sim_row["simulation_id"],),
    ).fetchone()[0]
    assert benchmark_count == 4  # 2 benchmark ticks x 2 opponents


def test_catalog_file_skips_database_without_simulation_config(tmp_path):
    db_path = tmp_path / "not_a_run.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()

    analytics_conn = open_analytics_db(str(tmp_path / "analytics.db"))
    cataloged = catalog_file(analytics_conn, db_path)

    assert cataloged is False
    assert analytics_conn.execute("SELECT COUNT(*) FROM simulations").fetchone()[0] == 0


# -- 1.3 directory-scanning CLI ---------------------------------------------------


def test_run_catalog_produces_one_row_per_run(tmp_path):
    config = _test_config(population_size=6, benchmark_every_n_ticks=2, benchmark_games_per_opponent=3)
    run(ticks=4, seed=1, db_path=str(tmp_path / "run1.db"), config=config)
    run(ticks=4, seed=2, db_path=str(tmp_path / "run2.db"), config=config)

    analytics_db_path = tmp_path / "analytics.db"
    cataloged = run_catalog(str(tmp_path), str(analytics_db_path))

    assert len(cataloged) == 2
    conn = sqlite3.connect(str(analytics_db_path))
    assert conn.execute("SELECT COUNT(*) FROM simulations").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM simulation_population_snapshots").fetchone()[0] == 8
    assert conn.execute("SELECT COUNT(*) FROM simulation_benchmark_results").fetchone()[0] == 8


def test_run_catalog_excludes_analytics_db_from_scan(tmp_path):
    config = _test_config(population_size=6)
    run(ticks=2, seed=1, db_path=str(tmp_path / "run1.db"), config=config)

    analytics_db_path = tmp_path / "analytics.db"
    # First pass creates analytics.db inside the same directory being scanned.
    run_catalog(str(tmp_path), str(analytics_db_path))
    # Second pass must not treat analytics.db itself as a run database.
    cataloged = run_catalog(str(tmp_path), str(analytics_db_path))

    assert cataloged == []


# -- 1.4 idempotency ---------------------------------------------------------------


def test_run_catalog_is_a_noop_on_unchanged_runs(tmp_path):
    config = _test_config(population_size=6)
    run(ticks=3, seed=1, db_path=str(tmp_path / "run1.db"), config=config)

    analytics_db_path = tmp_path / "analytics.db"
    first = run_catalog(str(tmp_path), str(analytics_db_path))
    second = run_catalog(str(tmp_path), str(analytics_db_path))

    assert len(first) == 1
    assert second == []

    conn = sqlite3.connect(str(analytics_db_path))
    assert conn.execute("SELECT COUNT(*) FROM simulations").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM simulation_population_snapshots").fetchone()[0] == 3


def test_run_catalog_picks_up_an_advanced_run_without_duplicating(tmp_path):
    config = _test_config(population_size=6)
    db_path = str(tmp_path / "run1.db")
    run(ticks=3, seed=1, db_path=db_path, config=config)

    analytics_db_path = tmp_path / "analytics.db"
    run_catalog(str(tmp_path), str(analytics_db_path))

    conn = sqlite3.connect(str(analytics_db_path))
    conn.row_factory = sqlite3.Row
    simulation_id = conn.execute("SELECT simulation_id FROM simulations").fetchone()["simulation_id"]
    before_ticks = {
        r["tick"] for r in conn.execute(
            "SELECT tick FROM simulation_population_snapshots WHERE simulation_id = ?", (simulation_id,)
        )
    }
    assert before_ticks == {1, 2, 3}

    run(ticks=2, seed=None, db_path=db_path, config=config)  # resume, 2 more ticks
    cataloged = run_catalog(str(tmp_path), str(analytics_db_path))

    assert len(cataloged) == 1
    conn = sqlite3.connect(str(analytics_db_path))
    conn.row_factory = sqlite3.Row
    after_rows = list(
        conn.execute(
            "SELECT tick FROM simulation_population_snapshots WHERE simulation_id = ? ORDER BY tick",
            (simulation_id,),
        )
    )
    after_ticks = [r["tick"] for r in after_rows]
    assert after_ticks == [1, 2, 3, 4, 5]  # old ticks intact, not duplicated; new ticks added

    last_cataloged_tick = conn.execute(
        "SELECT last_cataloged_tick FROM simulations WHERE simulation_id = ?", (simulation_id,)
    ).fetchone()["last_cataloged_tick"]
    assert last_cataloged_tick == 5
