"""Minimal agent: wraps a genome + the network built from it.

No live-stats (games_played/wins/fitness) and no mutable live-weights for
somatic mutation -- both need a database (Phase 3) or a running tick loop
(Phase 4) to mean anything, and are deliberately deferred (plan Sec4.7).
"""

from __future__ import annotations

import numpy as np

from evoconnect4.agent.genome import Genome
from evoconnect4.agent.network import Network
from evoconnect4.game.connect_four import Board


class Agent:
    def __init__(self, genome: Genome, columns: int, rows: int) -> None:
        self.genome = genome
        self.columns = columns
        self.rows = rows
        hidden_size = genome.hidden_layer_sizes[0]
        self.network = Network(
            genome.weights,
            input_size=columns * rows,
            hidden_size=hidden_size,
            output_size=columns,
        )

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
