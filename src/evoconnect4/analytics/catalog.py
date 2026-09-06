"""Cross-simulation catalog: rolls up aggregate-only data from many run
databases into a shared analytics.db (plan Sec7 extension, Phase 7).

Reads source run databases through plain, read-only sqlite3 connections --
deliberately not through Repository/schema.py, so scanning a directory of
files never creates or modifies anything in those source files.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ANALYTICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS simulations (
    simulation_id TEXT PRIMARY KEY,
    source_db_path TEXT NOT NULL,
    cataloged_at TEXT NOT NULL,
    last_cataloged_tick INTEGER NOT NULL,
    board_columns INTEGER NOT NULL,
    board_rows INTEGER NOT NULL,
    hidden_layer_sizes TEXT NOT NULL,
    weight_init_std REAL NOT NULL,
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

CREATE TABLE IF NOT EXISTS simulation_population_snapshots (
    id INTEGER PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    population_size INTEGER NOT NULL,
    avg_fitness REAL NOT NULL,
    max_fitness REAL NOT NULL,
    min_fitness REAL NOT NULL,
    avg_lifespan REAL NOT NULL,
    avg_mutation_rate REAL NOT NULL,
    source_best_agent_id INTEGER,
    UNIQUE(simulation_id, tick)
);

CREATE TABLE IF NOT EXISTS simulation_benchmark_results (
    id INTEGER PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    opponent_type TEXT NOT NULL,
    games_played INTEGER NOT NULL,
    win_rate REAL NOT NULL,
    source_agent_id INTEGER,
    UNIQUE(simulation_id, tick, opponent_type)
);
"""

_SIMULATIONS_COLUMNS = (
    "simulation_id", "source_db_path", "cataloged_at", "last_cataloged_tick",
    "board_columns", "board_rows", "hidden_layer_sizes", "weight_init_std",
    "population_size", "lifespan_range", "lifespan_mutation_scale",
    "mutation_rate_range", "mutation_rate_tau", "crossover_rate_range",
    "crossover_rate_mutation_std", "tournament_size",
    "reproduction_interval_min", "reproduction_interval_max",
    "games_per_pair_per_tick", "benchmark_every_n_ticks",
    "benchmark_games_per_opponent", "random_seed", "cull_fraction_range",
    "cull_fraction_beta_a", "cull_fraction_beta_b", "cull_allow_immature_offspring",
)


def create_analytics_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_ANALYTICS_SCHEMA)


def open_analytics_db(analytics_db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(analytics_db_path)
    conn.row_factory = sqlite3.Row
    create_analytics_schema(conn)
    return conn


def _read_source(db_path: Path) -> dict[str, Any] | None:
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError:
        return None

    try:
        config_row = conn.execute("SELECT * FROM simulation_config WHERE id = 1").fetchone()
        if config_row is None:
            return None
        history_row = conn.execute(
            "SELECT * FROM simulation_config_history WHERE tick = 0"
        ).fetchone()
        if history_row is None:
            return None
        state_row = conn.execute("SELECT * FROM simulation_state WHERE id = 1").fetchone()
        current_tick = state_row["current_tick"] if state_row is not None else 0

        return {
            "simulation_id": config_row["simulation_id"],
            "frozen": dict(config_row),
            "initial_mutable": dict(history_row),
            "current_tick": current_tick,
            "snapshots": [dict(r) for r in conn.execute("SELECT * FROM population_snapshots")],
            "benchmark_results": [dict(r) for r in conn.execute("SELECT * FROM benchmark_results")],
        }
    except sqlite3.OperationalError:
        return None  # not a run database, or missing an expected table
    finally:
        conn.close()


def catalog_file(analytics_conn: sqlite3.Connection, db_path: Path) -> bool:
    """Catalog one run database. Returns True if (re-)cataloged, False if skipped."""
    source = _read_source(db_path)
    if source is None:
        return False

    simulation_id = source["simulation_id"]
    current_tick = source["current_tick"]

    existing = analytics_conn.execute(
        "SELECT last_cataloged_tick FROM simulations WHERE simulation_id = ?", (simulation_id,)
    ).fetchone()
    if existing is not None and existing["last_cataloged_tick"] >= current_tick:
        return False

    frozen = source["frozen"]
    initial = source["initial_mutable"]
    values = {
        "simulation_id": simulation_id,
        "source_db_path": str(db_path),
        "cataloged_at": datetime.now(timezone.utc).isoformat(),
        "last_cataloged_tick": current_tick,
        "board_columns": frozen["board_columns"],
        "board_rows": frozen["board_rows"],
        "hidden_layer_sizes": frozen["hidden_layer_sizes"],
        "weight_init_std": frozen["weight_init_std"],
        "population_size": initial["population_size"],
        "lifespan_range": initial["lifespan_range"],
        "lifespan_mutation_scale": initial["lifespan_mutation_scale"],
        "mutation_rate_range": initial["mutation_rate_range"],
        "mutation_rate_tau": initial["mutation_rate_tau"],
        "crossover_rate_range": initial["crossover_rate_range"],
        "crossover_rate_mutation_std": initial["crossover_rate_mutation_std"],
        "tournament_size": initial["tournament_size"],
        "reproduction_interval_min": initial["reproduction_interval_min"],
        "reproduction_interval_max": initial["reproduction_interval_max"],
        "games_per_pair_per_tick": initial["games_per_pair_per_tick"],
        "benchmark_every_n_ticks": initial["benchmark_every_n_ticks"],
        "benchmark_games_per_opponent": initial["benchmark_games_per_opponent"],
        "random_seed": initial["random_seed"],
        "cull_fraction_range": initial["cull_fraction_range"],
        "cull_fraction_beta_a": initial["cull_fraction_beta_a"],
        "cull_fraction_beta_b": initial["cull_fraction_beta_b"],
        "cull_allow_immature_offspring": initial["cull_allow_immature_offspring"],
    }
    placeholders = ", ".join("?" for _ in _SIMULATIONS_COLUMNS)
    update_clause = ", ".join(f"{col}=excluded.{col}" for col in _SIMULATIONS_COLUMNS if col != "simulation_id")
    analytics_conn.execute(
        f"""
        INSERT INTO simulations ({", ".join(_SIMULATIONS_COLUMNS)})
        VALUES ({placeholders})
        ON CONFLICT(simulation_id) DO UPDATE SET {update_clause}
        """,
        tuple(values[col] for col in _SIMULATIONS_COLUMNS),
    )

    for snap in source["snapshots"]:
        analytics_conn.execute(
            """
            INSERT OR REPLACE INTO simulation_population_snapshots (
                simulation_id, tick, population_size, avg_fitness, max_fitness,
                min_fitness, avg_lifespan, avg_mutation_rate, source_best_agent_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                simulation_id, snap["tick"], snap["population_size"], snap["avg_fitness"],
                snap["max_fitness"], snap["min_fitness"], snap["avg_lifespan"],
                snap["avg_mutation_rate"], snap["best_agent_id"],
            ),
        )

    for result in source["benchmark_results"]:
        analytics_conn.execute(
            """
            INSERT OR REPLACE INTO simulation_benchmark_results (
                simulation_id, tick, opponent_type, games_played, win_rate, source_agent_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                simulation_id, result["tick"], result["opponent_type"],
                result["games_played"], result["win_rate"], result["agent_id"],
            ),
        )

    analytics_conn.commit()
    return True


def run_catalog(runs_dir: str, analytics_db_path: str) -> list[Path]:
    """Scan runs_dir for *.db files and catalog each. Returns the list of files
    that were (re-)cataloged (skipped files are omitted)."""
    analytics_path = Path(analytics_db_path).resolve()
    analytics_dir = analytics_path.parent
    if analytics_dir != Path("."):
        analytics_dir.mkdir(parents=True, exist_ok=True)

    conn = open_analytics_db(str(analytics_path))
    try:
        cataloged = []
        for db_path in sorted(Path(runs_dir).glob("*.db")):
            if db_path.resolve() == analytics_path:
                continue
            if catalog_file(conn, db_path):
                cataloged.append(db_path)
        return cataloged
    finally:
        conn.close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Roll up aggregate data from EvoConnect4 run databases into a shared analytics.db."
    )
    parser.add_argument("--runs-dir", type=str, default="data", help="Directory to scan for run databases")
    parser.add_argument(
        "--analytics-db", type=str, default="data/analytics.db", help="Path to the shared analytics database"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    cataloged = run_catalog(args.runs_dir, args.analytics_db)
    print(f"Cataloged {len(cataloged)} run(s) into {args.analytics_db}")


if __name__ == "__main__":
    main()
