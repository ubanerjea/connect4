import numpy as np

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


def test_random_mover_is_deterministic_given_the_same_seeded_rng():
    board = Board(columns=7, rows=6)

    sequence_a = [random_mover(board, rng=np.random.default_rng(7)) for _ in range(20)]
    sequence_b = [random_mover(board, rng=np.random.default_rng(7)) for _ in range(20)]

    assert sequence_a == sequence_b
    assert all(isinstance(m, int) for m in sequence_a)


def test_heuristic_bot_is_deterministic_given_the_same_seeded_rng():
    board = Board()
    board._grid[1] = [1]
    board._grid[2] = [1]
    board._grid[3] = [1]
    board.current_player = 1
    # open three: both column 0 and column 4 win -- tie resolved by rng, not stdlib random

    sequence_a = [heuristic_bot(board, rng=np.random.default_rng(3)) for _ in range(20)]
    sequence_b = [heuristic_bot(board, rng=np.random.default_rng(3)) for _ in range(20)]

    assert sequence_a == sequence_b
    assert all(isinstance(m, int) for m in sequence_a)
