from evoconnect4.game.bots import heuristic_bot, random_mover
from evoconnect4.game.connect_four import Board


def test_random_mover_always_returns_a_legal_move():
    board = Board(columns=7, rows=2)
    board.drop(0)
    board.drop(0)  # column 0 now full
    for _ in range(50):
        move = random_mover(board)
        assert move in board.legal_moves()


def test_heuristic_bot_takes_immediate_win():
    board = Board()
    board._grid[0] = [1]
    board._grid[1] = [1]
    board._grid[2] = [1]
    board.current_player = 1
    assert heuristic_bot(board) == 3


def test_heuristic_bot_blocks_opponent_immediate_win():
    board = Board()
    board._grid[0] = [-1]
    board._grid[1] = [-1]
    board._grid[2] = [-1]
    board.current_player = 1
    assert heuristic_bot(board) == 3


def test_heuristic_bot_prefers_center_with_no_win_or_block():
    board = Board()
    assert heuristic_bot(board) == 3
