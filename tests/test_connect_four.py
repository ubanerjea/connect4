import pytest

from evoconnect4.game.connect_four import Board


def test_new_board_is_empty_with_default_dimensions():
    board = Board()
    assert board.columns == 7
    assert board.rows == 6
    for c in range(board.columns):
        for r in range(board.rows):
            assert board.cell(c, r) == 0


def test_drop_stacks_pieces_bottom_up():
    board = Board()
    board.drop(3)
    board.drop(3)
    assert board.cell(3, 0) != 0
    assert board.cell(3, 1) != 0
    assert board.cell(3, 2) == 0


def test_legal_moves_excludes_full_column():
    board = Board(columns=7, rows=2)
    board.drop(0)
    board.drop(1)
    board.drop(0)
    assert 0 not in board.legal_moves()
    assert 1 in board.legal_moves()


def test_legal_moves_includes_nonfull_column():
    board = Board()
    assert set(board.legal_moves()) == set(range(board.columns))


def test_drop_to_full_column_raises_and_does_not_mutate():
    board = Board(columns=7, rows=1)
    board.drop(0)
    snapshot = [board.cell(0, r) for r in range(board.rows)]
    with pytest.raises(ValueError):
        board.drop(0)
    assert [board.cell(0, r) for r in range(board.rows)] == snapshot


def test_drop_out_of_range_raises_and_does_not_mutate():
    board = Board()
    with pytest.raises(ValueError):
        board.drop(board.columns)
    with pytest.raises(ValueError):
        board.drop(-1)
    for c in range(board.columns):
        for r in range(board.rows):
            assert board.cell(c, r) == 0


def test_turn_alternates_after_accepted_move():
    board = Board()
    first = board.current_player
    board.drop(0)
    assert board.current_player == -first


def test_turn_does_not_alternate_after_rejected_move():
    board = Board(columns=7, rows=1)
    board.drop(0)
    player_after_first_move = board.current_player
    with pytest.raises(ValueError):
        board.drop(0)
    assert board.current_player == player_after_first_move


def test_horizontal_win():
    board = Board()
    # P1 drops in 0,1,2 while P2 drops elsewhere (col 4); P1's 4th move completes the row.
    for col in (0, 4, 1, 4, 2, 4):
        board.drop(col)
    assert board.winner is None
    board.drop(3)
    assert board.winner == 1


def test_vertical_win():
    board = Board()
    for _ in range(3):
        board.drop(0)  # P1
        board.drop(1)  # P2
    assert board.winner is None
    board.drop(0)
    assert board.winner == 1


def test_diagonal_win_ascending():
    board = Board()
    # Shape the stacks directly so a "/" diagonal for P1 is one drop away at (3,3):
    # (0,0)=P1, (1,1)=P1 atop P2, (2,2)=P1 atop P2/P2, (3,3)=P1 atop P2/P2/P2.
    board._grid[0] = [1]
    board._grid[1] = [-1, 1]
    board._grid[2] = [-1, -1, 1]
    board._grid[3] = [-1, -1, -1]
    board.current_player = 1
    board.drop(3)
    assert board.winner == 1


def test_diagonal_win_descending():
    board = Board()
    # Shape the stacks directly so a "\" diagonal for P1 is one drop away at (0,3):
    # (3,0)=P1, (2,1)=P1 atop P2, (1,2)=P1 atop P2/P2, (0,3)=P1 atop P2/P2/P2.
    board._grid[0] = [-1, -1, -1]
    board._grid[1] = [-1, -1, 1]
    board._grid[2] = [-1, 1]
    board._grid[3] = [1]
    board.current_player = 1
    board.drop(0)
    assert board.winner == 1


def test_draw_when_board_full_with_no_winner():
    board = Board(columns=2, rows=2)
    # 2x2 board -- too small for 4-in-a-row -- filled completely with no winner.
    board.drop(0)  # P1
    board.drop(0)  # P2
    board.drop(1)  # P1
    assert not board.is_over
    board.drop(1)  # P2 -> board full
    assert board.is_draw
    assert board.winner is None
    assert board.is_over
