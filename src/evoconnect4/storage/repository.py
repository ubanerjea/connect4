"""SQLite repository: agent/game CRUD, snapshot insert/read (plan Sec6/Sec7)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from evoconnect4.storage.schema import create_schema


def _row_to_agent(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    record["nn_weights"] = json.loads(record["nn_weights"])
    record["nn_architecture"] = json.loads(record["nn_architecture"])
    return record


def _row_to_game(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    record["move_history"] = json.loads(record["move_history"])
    return record


class Repository:
    def __init__(self, db_path: str = "data/evoconnect4.db") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        create_schema(self.conn)

    def __enter__(self) -> "Repository":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def commit(self) -> None:
        self.conn.commit()

    # -- agents ---------------------------------------------------------

    def insert_agent(
        self,
        *,
        parent1_id: int | None,
        parent2_id: int | None,
        generation: int,
        birth_tick: int,
        status: str,
        nn_weights: dict,
        nn_architecture: list,
        lifespan: int,
        mutation_rate: float,
        crossover_rate: float,
        games_played: int = 0,
        wins: int = 0,
        losses: int = 0,
        draws: int = 0,
        fitness: float = 0.0,
        games_since_last_reproduction: int = 0,
        offspring_count: int = 0,
        death_tick: int | None = None,
        death_cause: str | None = None,
        parent_avg_fitness: float = 0.0,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO agents (
                parent1_id, parent2_id, generation, birth_tick, death_tick,
                status, death_cause, nn_weights, nn_architecture, lifespan,
                mutation_rate, crossover_rate, games_played, wins, losses,
                draws, fitness, games_since_last_reproduction, offspring_count,
                parent_avg_fitness
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parent1_id,
                parent2_id,
                generation,
                birth_tick,
                death_tick,
                status,
                death_cause,
                json.dumps(nn_weights),
                json.dumps(nn_architecture),
                lifespan,
                mutation_rate,
                crossover_rate,
                games_played,
                wins,
                losses,
                draws,
                fitness,
                games_since_last_reproduction,
                offspring_count,
                parent_avg_fitness,
            ),
        )
        return cursor.lastrowid

    def get_agent(self, agent_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        return _row_to_agent(row) if row else None

    def update_agent_stats(
        self,
        agent_id: int,
        *,
        games_played: int,
        wins: int,
        losses: int,
        draws: int,
        fitness: float,
        games_since_last_reproduction: int,
    ) -> None:
        self.conn.execute(
            """
            UPDATE agents
            SET games_played = ?, wins = ?, losses = ?, draws = ?, fitness = ?,
                games_since_last_reproduction = ?
            WHERE agent_id = ?
            """,
            (games_played, wins, losses, draws, fitness, games_since_last_reproduction, agent_id),
        )

    def mark_agent_dead(self, agent_id: int, death_tick: int, death_cause: str) -> None:
        self.conn.execute(
            "UPDATE agents SET status = 'dead', death_tick = ?, death_cause = ? WHERE agent_id = ?",
            (death_tick, death_cause, agent_id),
        )

    def list_agents(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = self.conn.execute("SELECT * FROM agents").fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM agents WHERE status = ?", (status,)).fetchall()
        return [_row_to_agent(row) for row in rows]

    # -- games ------------------------------------------------------------

    def insert_game(
        self,
        *,
        tick: int,
        player1_agent_id: int,
        player2_agent_id: int | None = None,
        result: str,
        num_moves: int,
        move_history: list[int],
        game_type: str,
        opponent_label: str | None = None,
    ) -> int:
        if game_type == "evolution":
            if player2_agent_id is None or opponent_label is not None:
                raise ValueError(
                    "game_type='evolution' requires both player1_agent_id and "
                    "player2_agent_id set, and no opponent_label"
                )
        else:
            if player1_agent_id is None or player2_agent_id is not None or opponent_label is None:
                raise ValueError(
                    f"game_type={game_type!r} requires player1_agent_id set (the agent), "
                    "player2_agent_id unset, and an opponent_label"
                )

        cursor = self.conn.execute(
            """
            INSERT INTO games (
                tick, player1_agent_id, player2_agent_id, result, num_moves,
                move_history, game_type, opponent_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tick,
                player1_agent_id,
                player2_agent_id,
                result,
                num_moves,
                json.dumps(move_history),
                game_type,
                opponent_label,
            ),
        )
        return cursor.lastrowid

    def get_game(self, game_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM games WHERE game_id = ?", (game_id,)).fetchone()
        return _row_to_game(row) if row else None

    def list_games(self, *, tick: int | None = None) -> list[dict[str, Any]]:
        if tick is None:
            rows = self.conn.execute("SELECT * FROM games").fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM games WHERE tick = ?", (tick,)).fetchall()
        return [_row_to_game(row) for row in rows]

    # -- population snapshots ----------------------------------------------

    def insert_snapshot(
        self,
        *,
        tick: int,
        population_size: int,
        avg_fitness: float,
        max_fitness: float,
        min_fitness: float,
        avg_lifespan: float,
        avg_mutation_rate: float,
        best_agent_id: int | None,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO population_snapshots (
                tick, population_size, avg_fitness, max_fitness, min_fitness,
                avg_lifespan, avg_mutation_rate, best_agent_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tick,
                population_size,
                avg_fitness,
                max_fitness,
                min_fitness,
                avg_lifespan,
                avg_mutation_rate,
                best_agent_id,
            ),
        )
        return cursor.lastrowid

    def get_latest_snapshot(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM population_snapshots ORDER BY tick DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def list_snapshots(self, *, tick: int | None = None) -> list[dict[str, Any]]:
        if tick is None:
            rows = self.conn.execute("SELECT * FROM population_snapshots ORDER BY tick").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM population_snapshots WHERE tick = ? ORDER BY tick", (tick,)
            ).fetchall()
        return [dict(row) for row in rows]

    # -- simulation config / history / state -------------------------------

    def insert_simulation_config(
        self,
        *,
        simulation_id: str,
        board_columns: int,
        board_rows: int,
        hidden_layer_sizes: list,
        weight_init_std: float,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO simulation_config (
                id, simulation_id, board_columns, board_rows,
                hidden_layer_sizes, weight_init_std
            ) VALUES (1, ?, ?, ?, ?, ?)
            """,
            (simulation_id, board_columns, board_rows, json.dumps(hidden_layer_sizes), weight_init_std),
        )

    def get_simulation_config(self) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM simulation_config WHERE id = 1").fetchone()
        if row is None:
            return None
        record = dict(row)
        record["hidden_layer_sizes"] = json.loads(record["hidden_layer_sizes"])
        return record

    def insert_simulation_config_history_row(
        self,
        *,
        tick: int,
        population_size: int,
        lifespan_range: tuple[int, int],
        lifespan_mutation_scale: float,
        mutation_rate_range: tuple[float, float],
        mutation_rate_tau: float,
        crossover_rate_range: tuple[float, float],
        crossover_rate_mutation_std: float,
        tournament_size: int,
        reproduction_interval_min: int,
        reproduction_interval_max: int,
        games_per_pair_per_tick: int,
        benchmark_every_n_ticks: int,
        benchmark_games_per_opponent: int,
        random_seed: int,
        cull_fraction_range: tuple[float, float],
        cull_fraction_beta_a: float,
        cull_fraction_beta_b: float,
        cull_allow_immature_offspring: bool,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO simulation_config_history (
                tick, population_size, lifespan_range, lifespan_mutation_scale,
                mutation_rate_range, mutation_rate_tau, crossover_rate_range,
                crossover_rate_mutation_std, tournament_size,
                reproduction_interval_min, reproduction_interval_max,
                games_per_pair_per_tick, benchmark_every_n_ticks,
                benchmark_games_per_opponent, random_seed, cull_fraction_range,
                cull_fraction_beta_a, cull_fraction_beta_b,
                cull_allow_immature_offspring
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tick,
                population_size,
                json.dumps(list(lifespan_range)),
                lifespan_mutation_scale,
                json.dumps(list(mutation_rate_range)),
                mutation_rate_tau,
                json.dumps(list(crossover_rate_range)),
                crossover_rate_mutation_std,
                tournament_size,
                reproduction_interval_min,
                reproduction_interval_max,
                games_per_pair_per_tick,
                benchmark_every_n_ticks,
                benchmark_games_per_opponent,
                random_seed,
                json.dumps(list(cull_fraction_range)),
                cull_fraction_beta_a,
                cull_fraction_beta_b,
                int(cull_allow_immature_offspring),
            ),
        )
        return cursor.lastrowid

    def get_effective_config_at_tick(self, tick: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT * FROM simulation_config_history
            WHERE tick <= ? ORDER BY tick DESC LIMIT 1
            """,
            (tick,),
        ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["lifespan_range"] = tuple(json.loads(record["lifespan_range"]))
        record["mutation_rate_range"] = tuple(json.loads(record["mutation_rate_range"]))
        record["crossover_rate_range"] = tuple(json.loads(record["crossover_rate_range"]))
        record["cull_fraction_range"] = tuple(json.loads(record["cull_fraction_range"]))
        record["cull_allow_immature_offspring"] = bool(record["cull_allow_immature_offspring"])
        return record

    def upsert_simulation_state(self, *, current_tick: int, rng_state: str) -> None:
        self.conn.execute(
            """
            INSERT INTO simulation_state (id, current_tick, rng_state) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET current_tick = excluded.current_tick, rng_state = excluded.rng_state
            """,
            (current_tick, rng_state),
        )

    def get_simulation_state(self) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM simulation_state WHERE id = 1").fetchone()
        return dict(row) if row else None

    # -- benchmark results ---------------------------------------------------

    def insert_benchmark_result(
        self,
        *,
        tick: int,
        agent_id: int,
        opponent_type: str,
        games_played: int,
        win_rate: float,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO benchmark_results (
                tick, agent_id, opponent_type, games_played, win_rate
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (tick, agent_id, opponent_type, games_played, win_rate),
        )
        return cursor.lastrowid

    def list_benchmark_results(self, *, tick: int | None = None) -> list[dict[str, Any]]:
        if tick is None:
            rows = self.conn.execute("SELECT * FROM benchmark_results").fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM benchmark_results WHERE tick = ?", (tick,)).fetchall()
        return [dict(row) for row in rows]
