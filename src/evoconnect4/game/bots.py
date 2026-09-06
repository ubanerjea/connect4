"""Deterministic move-choosing strategies (not agents -- no genome, no NN).

Plain functions with signature Board -> int, so they satisfy the same
chooser interface match.py expects of any move-choosing participant.
"""

from __future__ import annotations

import random

import numpy as np

from evoconnect4.game.connect_four import Board


def _choice(options: list[int], rng: np.random.Generator | None) -> int:
    if rng is not None:
        return int(rng.choice(options))
    return random.choice(options)


def random_mover(board: Board, rng: np.random.Generator | None = None) -> int:
    return _choice(board.legal_moves(), rng)


def heuristic_bot(board: Board, rng: np.random.Generator | None = None) -> int:
    legal = board.legal_moves()
    me = board.current_player
    opponent = -me

    winning = [c for c in legal if board.would_win(c, me)]
    if winning:
        return _choice(winning, rng)

    blocking = [c for c in legal if board.would_win(c, opponent)]
    if blocking:
        return _choice(blocking, rng)

    center = (board.columns - 1) / 2
    min_distance = min(abs(c - center) for c in legal)
    nearest = [c for c in legal if abs(c - center) == min_distance]
    return _choice(nearest, rng)
