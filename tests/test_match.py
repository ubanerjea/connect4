import pytest

from evoconnect4.game.bots import heuristic_bot, random_mover
from evoconnect4.game.match import play_match


def test_match_between_heuristic_and_random_completes():
    result = play_match(heuristic_bot, random_mover)
    assert result.winner in (1, -1, None)
    assert result.num_moves > 0


def test_move_history_length_matches_num_moves():
    result = play_match(heuristic_bot, random_mover)
    assert len(result.move_history) == result.num_moves


def test_first_mover_moves_first():
    calls = []

    def spy_chooser(board):
        calls.append(board.current_player)
        return random_mover(board)

    def other_chooser(board):
        calls.append(board.current_player)
        return random_mover(board)

    result = play_match(spy_chooser, other_chooser, first_mover=-1)
    assert calls[0] == -1
    assert len(calls) == result.num_moves


def test_illegal_move_from_chooser_propagates_value_error():
    # A chooser that always returns column 0 fills it (default board is 6 rows
    # deep) and then attempts an illegal move into the now-full column.
    def always_column_zero(board):
        return 0

    with pytest.raises(ValueError):
        play_match(always_column_zero, always_column_zero)
