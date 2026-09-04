"""SQLite repository: agent/game CRUD, snapshot insert/read (plan Sec6/Sec7).

benchmark_results has no reader/writer here -- Phase 6 owns that.
"""

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
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO agents (
                parent1_id, parent2_id, generation, birth_tick, death_tick,
                status, death_cause, nn_weights, nn_architecture, lifespan,
                mutation_rate, crossover_rate, games_played, wins, losses,
                draws, fitness, games_since_last_reproduction, offspring_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        player2_agent_id: int,
        result: str,
        num_moves: int,
        move_history: list[int],
        game_type: str,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO games (
                tick, player1_agent_id, player2_agent_id, result, num_moves,
                move_history, game_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tick,
                player1_agent_id,
                player2_agent_id,
                result,
                num_moves,
                json.dumps(move_history),
                game_type,
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
