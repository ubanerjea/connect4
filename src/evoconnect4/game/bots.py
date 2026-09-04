"""Deterministic move-choosing strategies (not agents -- no genome, no NN).

Plain functions with signature Board -> int, so they satisfy the same
chooser interface match.py expects of any move-choosing participant.
"""

from __future__ import annotations

import random

from evoconnect4.game.connect_four import Board


def random_mover(board: Board) -> int:
    return random.choice(board.legal_moves())


def heuristic_bot(board: Board) -> int:
    legal = board.legal_moves()
    me = board.current_player
    opponent = -me

    winning = [c for c in legal if board.would_win(c, me)]
    if winning:
        return random.choice(winning)

    blocking = [c for c in legal if board.would_win(c, opponent)]
    if blocking:
        return random.choice(blocking)

    center = (board.columns - 1) / 2
    min_distance = min(abs(c - center) for c in legal)
    nearest = [c for c in legal if abs(c - center) == min_distance]
    return random.choice(nearest)
