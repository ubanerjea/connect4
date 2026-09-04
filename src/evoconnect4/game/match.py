"""Plays one full Connect Four game between two move-choosing callables.

A chooser is anything callable as Board -> int -- a bare function today
(evoconnect4.game.bots), a real Agent's move method later. match.py never
needs to know which.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from evoconnect4.game.connect_four import Board

Chooser = Callable[[Board], int]


@dataclass
class MatchResult:
    winner: int | None
    move_history: list[int] = field(default_factory=list)

    @property
    def num_moves(self) -> int:
        return len(self.move_history)


def play_match(chooser_a: Chooser, chooser_b: Chooser, first_mover: int = 1) -> MatchResult:
    board = Board()
    board.current_player = first_mover
    choosers = {1: chooser_a, -1: chooser_b}

    move_history: list[int] = []
    while not board.is_over:
        chooser = choosers[board.current_player]
        column = chooser(board)
        board.drop(column)
        move_history.append(column)

    return MatchResult(winner=board.winner, move_history=move_history)
