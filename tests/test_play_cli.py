import dataclasses

import numpy as np
import pytest

from evoconnect4.agent.network import weight_count
from evoconnect4.config import load_config
from evoconnect4.game.match import MatchResult
from evoconnect4.interface import play_cli
from evoconnect4.interface.play_cli import (
    AgentSelectionError,
    QuitRequested,
    _parse_args,
    load_agent,
    make_human_chooser,
    play_one_game,
    prompt_yes_no,
    run_session,
    select_agent_record,
)
from evoconnect4.storage.repository import Repository

BASE_CONFIG = load_config()


def _test_config(**overrides):
    return dataclasses.replace(BASE_CONFIG, **overrides)


def _repo_with_agent(**agent_overrides) -> tuple[Repository, int]:
    repo = Repository(":memory:")
    repo.insert_simulation_config(
        simulation_id="sim-1",
        board_columns=BASE_CONFIG.board_columns,
        board_rows=BASE_CONFIG.board_rows,
        hidden_layer_sizes=BASE_CONFIG.hidden_layer_sizes,
        weight_init_std=BASE_CONFIG.weight_init_std,
    )
    fields = dict(
        parent1_id=None, parent2_id=None, generation=0, birth_tick=0, status="alive",
        nn_weights=[0.1] * weight_count(
            BASE_CONFIG.board_columns * BASE_CONFIG.board_rows, BASE_CONFIG.hidden_layer_sizes[0], BASE_CONFIG.board_columns
        ),
        nn_architecture=BASE_CONFIG.hidden_layer_sizes,
        lifespan=100, mutation_rate=0.1, crossover_rate=0.5, fitness=0.5,
    )
    fields.update(agent_overrides)
    agent_id = repo.insert_agent(**fields)
    return repo, agent_id


class _StubAgent:
    """A duck-typed stand-in for Agent with fully scripted moves, for deterministic game tests."""

    def __init__(self, agent_id: int, columns: list[int]) -> None:
        self.agent_id = agent_id
        self._columns = iter(columns)

    def choose_move(self, board) -> int:
        return next(self._columns)


def _scripted_input(responses: list[str]):
    it = iter(responses)

    def input_fn(prompt: str) -> str:
        return next(it)

    return input_fn


# -- 1.1 agent selection ------------------------------------------------------


def test_select_agent_record_by_id():
    repo, agent_id = _repo_with_agent()
    record = select_agent_record(repo, str(agent_id))
    assert record["agent_id"] == agent_id


def test_select_agent_record_by_id_missing_raises():
    repo, _ = _repo_with_agent()
    with pytest.raises(AgentSelectionError):
        select_agent_record(repo, "999999")


def test_select_agent_record_best_alive_picks_highest_fitness():
    repo, _ = _repo_with_agent(fitness=0.2)
    # add a second, fitter alive agent to the same repo
    fields = dict(
        parent1_id=None, parent2_id=None, generation=0, birth_tick=0, status="alive",
        nn_weights=[0.1] * weight_count(
            BASE_CONFIG.board_columns * BASE_CONFIG.board_rows, BASE_CONFIG.hidden_layer_sizes[0], BASE_CONFIG.board_columns
        ),
        nn_architecture=BASE_CONFIG.hidden_layer_sizes,
        lifespan=100, mutation_rate=0.1, crossover_rate=0.5, fitness=0.9,
    )
    fitter_id = repo.insert_agent(**fields)

    record = select_agent_record(repo, "best-alive")
    assert record["agent_id"] == fitter_id


def test_select_agent_record_best_alive_excludes_dead():
    repo, dead_id = _repo_with_agent(fitness=0.9, status="dead", death_tick=1, death_cause="old_age")
    with pytest.raises(AgentSelectionError):
        select_agent_record(repo, "best-alive")


def test_select_agent_record_best_ever_includes_dead():
    repo, dead_id = _repo_with_agent(fitness=0.9, status="dead", death_tick=1, death_cause="old_age")
    record = select_agent_record(repo, "best-ever")
    assert record["agent_id"] == dead_id


def test_select_agent_record_best_ever_empty_database_raises():
    repo = Repository(":memory:")
    with pytest.raises(AgentSelectionError):
        select_agent_record(repo, "best-ever")


def test_select_agent_record_unrecognized_value_raises():
    repo, _ = _repo_with_agent()
    with pytest.raises(AgentSelectionError):
        select_agent_record(repo, "not-a-real-mode")


# -- 1.2 board-dimension sourcing ----------------------------------------------


def test_load_agent_uses_simulation_config_board_dimensions_not_live_config():
    custom_columns, custom_rows = 5, 4
    hidden = BASE_CONFIG.hidden_layer_sizes[0]
    repo = Repository(":memory:")
    repo.insert_simulation_config(
        simulation_id="sim-custom",
        board_columns=custom_columns,
        board_rows=custom_rows,
        hidden_layer_sizes=[hidden],
        weight_init_std=BASE_CONFIG.weight_init_std,
    )
    weights = [0.05] * weight_count(custom_columns * custom_rows, hidden, custom_columns)
    agent_id = repo.insert_agent(
        parent1_id=None, parent2_id=None, generation=0, birth_tick=0, status="alive",
        nn_weights=weights, nn_architecture=[hidden],
        lifespan=100, mutation_rate=0.1, crossover_rate=0.5,
    )

    # Sanity: the live BASE_CONFIG's board dimensions differ from this database's.
    assert (BASE_CONFIG.board_columns, BASE_CONFIG.board_rows) != (custom_columns, custom_rows)

    agent = load_agent(repo, str(agent_id))

    assert agent.network.w1.shape == (custom_columns * custom_rows, hidden)
    assert agent.network.w2.shape == (hidden, custom_columns)


def test_load_agent_raises_when_no_simulation_config():
    repo = Repository(":memory:")
    agent_id = repo.insert_agent(
        parent1_id=None, parent2_id=None, generation=0, birth_tick=0, status="alive",
        nn_weights=[0.1] * weight_count(42, 24, 7), nn_architecture=[24],
        lifespan=100, mutation_rate=0.1, crossover_rate=0.5,
    )
    with pytest.raises(AgentSelectionError):
        load_agent(repo, str(agent_id))


# -- 2.1 human input validation -------------------------------------------------


def test_human_chooser_returns_legal_move():
    from evoconnect4.game.connect_four import Board

    board = Board()
    chooser = make_human_chooser(input_fn=_scripted_input(["1"]), print_fn=lambda s: None)
    assert chooser(board) == 0  # 1-indexed "1" -> 0-indexed column 0


def test_human_chooser_reprompts_on_non_integer_input():
    from evoconnect4.game.connect_four import Board

    board = Board()
    chooser = make_human_chooser(input_fn=_scripted_input(["abc", "3"]), print_fn=lambda s: None)
    assert chooser(board) == 2


def test_human_chooser_reprompts_on_out_of_range_column():
    from evoconnect4.game.connect_four import Board

    board = Board()
    chooser = make_human_chooser(input_fn=_scripted_input(["99", "2"]), print_fn=lambda s: None)
    assert chooser(board) == 1


def test_human_chooser_reprompts_on_full_column():
    from evoconnect4.game.connect_four import Board

    board = Board(columns=7, rows=1)  # column 0 fills after a single drop
    board.drop(0)
    chooser = make_human_chooser(input_fn=_scripted_input(["1", "2"]), print_fn=lambda s: None)
    assert chooser(board) == 1


def test_prompt_yes_no_reprompts_on_invalid_answer():
    assert prompt_yes_no("?", input_fn=_scripted_input(["maybe", "y"]), print_fn=lambda s: None) is True
    assert prompt_yes_no("?", input_fn=_scripted_input(["n"]), print_fn=lambda s: None) is False


# -- 2.2 quit handling -----------------------------------------------------------


def test_human_chooser_raises_quit_requested():
    from evoconnect4.game.connect_four import Board

    board = Board()
    chooser = make_human_chooser(input_fn=_scripted_input(["quit"]), print_fn=lambda s: None)
    with pytest.raises(QuitRequested):
        chooser(board)


def test_run_session_quit_mid_game_writes_no_games_row():
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[0, 0, 0, 0, 0])
    # "n" (don't move first) then immediately quit on the human's turn
    input_fn = _scripted_input(["Tester", "n", "quit"])

    run_session(repo, stub, input_fn=input_fn, print_fn=lambda s: None)

    assert repo.list_games() == []


def test_run_session_keyboard_interrupt_mid_game_writes_no_games_row():
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[0, 0, 0, 0, 0])
    responses = iter(["Tester", "n"])

    def input_fn(prompt: str) -> str:
        try:
            return next(responses)
        except StopIteration:
            raise KeyboardInterrupt()

    run_session(repo, stub, input_fn=input_fn, print_fn=lambda s: None)

    assert repo.list_games() == []


# -- 3.1 single-game play loop: win and draw -------------------------------------


def test_play_one_game_human_win_is_detected_and_reported():
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[1, 1, 1, 1, 1])  # never blocks column 0

    messages = []
    # move first = yes; then drop column 1 (index 0) four times to win vertically
    input_fn = _scripted_input(["y", "1", "1", "1", "1"])
    result = play_one_game(stub, input_fn=input_fn, print_fn=messages.append)

    assert result.winner == -1  # human is always chooser_b / board position -1
    assert any("You win!" in m for m in messages)


def test_play_one_game_draw_is_detected_and_reported(monkeypatch):
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[])

    draw_result = MatchResult(winner=None, move_history=[0, 1, 2, 3, 4, 5, 6])
    monkeypatch.setattr(play_cli, "play_match", lambda *a, **k: draw_result)

    messages = []
    input_fn = _scripted_input(["y"])  # first-mover question only; play_match is mocked
    result = play_one_game(stub, input_fn=input_fn, print_fn=messages.append)

    assert result.winner is None
    assert any("draw" in m.lower() for m in messages)


# -- 4.1 session loop & game logging ----------------------------------------------


def test_run_session_logs_completed_game_with_expected_fields():
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[1, 1, 1, 1, 1])
    input_fn = _scripted_input(["Alice", "y", "1", "1", "1", "1", "n"])

    run_session(repo, stub, input_fn=input_fn, print_fn=lambda s: None)

    games = repo.list_games()
    assert len(games) == 1
    game = games[0]
    assert game["game_type"] == "human_vs_agent"
    assert game["player1_agent_id"] == agent_id
    assert game["player2_agent_id"] is None
    assert game["opponent_label"] == "Alice"
    assert game["result"] == "player2_win"  # human (chooser_b) won
    # human (col 0) and stub agent (col 1) alternate turns, human moving first
    assert game["move_history"] == [0, 1, 0, 1, 0, 1, 0]


def test_run_session_defaults_name_when_blank():
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[1, 1, 1, 1, 1])
    input_fn = _scripted_input(["", "y", "1", "1", "1", "1", "n"])

    run_session(repo, stub, input_fn=input_fn, print_fn=lambda s: None)

    assert repo.list_games()[0]["opponent_label"] == "Anonymous Human"


def test_run_session_does_not_alter_agent_official_record():
    repo, agent_id = _repo_with_agent()
    before = repo.get_agent(agent_id)
    stub = _StubAgent(agent_id, columns=[1, 1, 1, 1, 1])
    input_fn = _scripted_input(["Alice", "y", "1", "1", "1", "1", "n"])

    run_session(repo, stub, input_fn=input_fn, print_fn=lambda s: None)

    after = repo.get_agent(agent_id)
    assert after["games_played"] == before["games_played"]
    assert after["wins"] == before["wins"]
    assert after["losses"] == before["losses"]
    assert after["draws"] == before["draws"]
    assert after["fitness"] == before["fitness"]


def test_run_session_declining_play_again_ends_session_after_one_game():
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    input_fn = _scripted_input(["Alice", "y", "1", "1", "1", "1", "n"])

    run_session(repo, stub, input_fn=input_fn, print_fn=lambda s: None)

    assert len(repo.list_games()) == 1


def test_run_session_play_again_yes_starts_a_second_game():
    repo, agent_id = _repo_with_agent()
    stub = _StubAgent(agent_id, columns=[1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    input_fn = _scripted_input(
        ["Alice", "y", "1", "1", "1", "1", "y", "y", "1", "1", "1", "1", "n"]
    )

    run_session(repo, stub, input_fn=input_fn, print_fn=lambda s: None)

    assert len(repo.list_games()) == 2


# -- 4.2 CLI entry point ----------------------------------------------------------


def test_parse_args_reads_db_and_agent():
    args = _parse_args(["--db", "some.db", "--agent", "best-alive"])
    assert args.db == "some.db"
    assert args.agent == "best-alive"


def test_main_exits_cleanly_on_agent_selection_error():
    with pytest.raises(SystemExit) as exc_info:
        play_cli.main(["--db", ":memory:", "--agent", "best-alive"])
    assert exc_info.value.code == 1
