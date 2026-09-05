"""Agent: wraps a genome + the network built from it + live stats.

Live-stats (games_played/wins/losses/draws/fitness/games_since_last_reproduction)
are population/evolution bookkeeping (Phase 4), not game-specific -- unlike a
mutable live-weights copy for somatic mutation, which stays deferred to Phase 9.
"""

from __future__ import annotations

import numpy as np

from evoconnect4.agent.genome import Genome
from evoconnect4.agent.network import Network
from evoconnect4.game.connect_four import Board


class Agent:
    def __init__(
        self,
        genome: Genome,
        columns: int,
        rows: int,
        agent_id: int | None = None,
        generation: int = 0,
        parent1_id: int | None = None,
        parent2_id: int | None = None,
        parent_avg_fitness: float = 0.0,
    ) -> None:
        self.genome = genome
        self.columns = columns
        self.rows = rows
        self.agent_id = agent_id
        self.generation = generation
        self.parent1_id = parent1_id
        self.parent2_id = parent2_id
        self.parent_avg_fitness = parent_avg_fitness
        hidden_size = genome.hidden_layer_sizes[0]
        self.network = Network(
            genome.weights,
            input_size=columns * rows,
            hidden_size=hidden_size,
            output_size=columns,
        )

        self.games_played = 0
        self.wins = 0
        self.losses = 0
        self.draws = 0
        self.fitness = 0.0
        self.games_since_last_reproduction = 0

    def choose_move(self, board: Board) -> int:
        x = self._encode(board)
        scores = self.network.forward(x)
        legal = board.legal_moves()
        return max(legal, key=lambda c: scores[c])

    def _encode(self, board: Board) -> np.ndarray:
        values = [
            board.cell(c, r) * board.current_player
            for c in range(board.columns)
            for r in range(board.rows)
        ]
        return np.array(values, dtype=float)
