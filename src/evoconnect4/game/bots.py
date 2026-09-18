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


def _threats_after(board: Board, col: int, player: int) -> int:
    """Count winning threats the player would have after dropping in col (excluding col itself)."""
    board._grid[col].append(player)
    try:
        remaining = board.legal_moves()
        return sum(1 for c in remaining if c != col and board.would_win(c, player))
    finally:
        board._grid[col].pop()


def tactical_heuristic_bot(board: Board, rng: np.random.Generator | None = None) -> int:
    legal = board.legal_moves()
    me = board.current_player
    opponent = -me

    # 1. Win immediately
    winning = [c for c in legal if board.would_win(c, me)]
    if winning:
        return _choice(winning, rng)

    # 2. Block opponent's 1-ply win
    blocking = [c for c in legal if board.would_win(c, opponent)]
    if blocking:
        return _choice(blocking, rng)

    # 3. Create a fork
    fork_creating = [c for c in legal if _threats_after(board, c, me) >= 2]
    if fork_creating:
        return _choice(fork_creating, rng)

    # 4. Block opponent's fork
    fork_blocking = [c for c in legal if _threats_after(board, c, opponent) >= 2]
    if fork_blocking:
        return _choice(fork_blocking, rng)

    # 5. Center preference
    center = (board.columns - 1) / 2
    min_distance = min(abs(c - center) for c in legal)
    nearest = [c for c in legal if abs(c - center) == min_distance]
    return _choice(nearest, rng)


def get_heuristic_bot(level: str):
    if level == "basic":
        return heuristic_bot
    if level == "tactical":
        return tactical_heuristic_bot
    raise ValueError(f"Unknown heuristic_bot_level: {level!r}; expected 'basic' or 'tactical'")
