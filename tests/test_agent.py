import numpy as np

from evoconnect4.agent.agent import Agent
from evoconnect4.agent.genome import random_genome
from evoconnect4.config import load_config
from evoconnect4.game.bots import random_mover
from evoconnect4.game.connect_four import Board
from evoconnect4.game.match import play_match

CONFIG = load_config()
RNG = np.random.default_rng(42)


def _make_agent() -> Agent:
    genome = random_genome(CONFIG, rng=RNG)
    return Agent(genome, CONFIG.board_columns, CONFIG.board_rows)


def test_agent_constructs_from_a_random_genome():
    agent = _make_agent()
    assert agent.network is not None


def test_agent_live_stats_default_to_zero():
    agent = _make_agent()
    assert agent.agent_id is None
    assert agent.generation == 0
    assert agent.parent1_id is None
    assert agent.parent2_id is None
    assert agent.parent_avg_fitness == 0.0
    assert agent.games_played == 0
    assert agent.wins == 0
    assert agent.losses == 0
    assert agent.draws == 0
    assert agent.fitness == 0.0
    assert agent.games_since_last_reproduction == 0


def test_agent_always_chooses_a_legal_move():
    agent = _make_agent()

    boards = [Board(), Board(columns=7, rows=6)]
    board = Board()
    for col in (0, 1, 2, 3, 0, 1):
        board.drop(col)
    boards.append(board)

    for b in boards:
        move = agent.choose_move(b)
        assert move in b.legal_moves()


def test_move_choice_is_independent_of_player_identity():
    agent = _make_agent()

    board_a = Board()
    board_a._grid[2] = [1, -1]
    board_a._grid[3] = [-1]
    board_a.current_player = 1

    board_b = Board()
    board_b._grid[2] = [-1, 1]
    board_b._grid[3] = [1]
    board_b.current_player = -1

    assert agent.choose_move(board_a) == agent.choose_move(board_b)


def test_agent_can_play_a_full_match_via_play_match():
    agent = _make_agent()
    result = play_match(agent.choose_move, random_mover)
    assert result.winner in (1, -1, None)
    assert result.num_moves > 0
