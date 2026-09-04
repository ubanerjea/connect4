"""Connect Four rules engine: board state, legal moves, win/draw detection.

Pure logic, no I/O. Cells are +1 (player A) / -1 (player B) / 0 (empty) so
that a relative "own discs / opponent discs" view (Phase 2's NN input) is
just `board * current_player`.
"""

from __future__ import annotations

_DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))
_WIN_LENGTH = 4


class Board:
    def __init__(self, columns: int = 7, rows: int = 6) -> None:
        self.columns = columns
        self.rows = rows
        self._grid: list[list[int]] = [[] for _ in range(columns)]
        self.current_player: int = 1
        self.winner: int | None = None
        self.is_draw: bool = False

    @property
    def is_over(self) -> bool:
        return self.winner is not None or self.is_draw

    def legal_moves(self) -> list[int]:
        return [c for c in range(self.columns) if len(self._grid[c]) < self.rows]

    def cell(self, column: int, row: int) -> int:
        stack = self._grid[column]
        return stack[row] if row < len(stack) else 0

    def drop(self, column: int) -> None:
        if column < 0 or column >= self.columns or len(self._grid[column]) >= self.rows:
            raise ValueError(f"illegal move: column {column}")

        player = self.current_player
        row = len(self._grid[column])
        self._grid[column].append(player)

        if self._is_winning_move(column, row, player):
            self.winner = player
        elif all(len(stack) >= self.rows for stack in self._grid):
            self.is_draw = True

        self.current_player = -player

    def would_win(self, column: int, player: int) -> bool:
        row = len(self._grid[column])
        self._grid[column].append(player)
        try:
            return self._is_winning_move(column, row, player)
        finally:
            self._grid[column].pop()

    def _is_winning_move(self, column: int, row: int, player: int) -> bool:
        for dcol, drow in _DIRECTIONS:
            count = 1
            count += self._count_direction(column, row, dcol, drow, player)
            count += self._count_direction(column, row, -dcol, -drow, player)
            if count >= _WIN_LENGTH:
                return True
        return False

    def _count_direction(self, column: int, row: int, dcol: int, drow: int, player: int) -> int:
        count = 0
        c, r = column + dcol, row + drow
        while 0 <= c < self.columns and 0 <= r < self.rows and self.cell(c, r) == player:
            count += 1
            c += dcol
            r += drow
        return count
