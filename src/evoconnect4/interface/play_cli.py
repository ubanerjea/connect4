"""Human-vs-agent terminal CLI (plan Sec8, Phase 8).

A human plays a full, correctly-ruled game against a saved agent. Games
are logged as exhibitions (game_type='human_vs_agent') and never affect
the agent's official evolutionary record -- same treatment as Phase 6's
benchmark games.
"""

from __future__ import annotations

import argparse
from typing import Callable

from evoconnect4.agent.agent import Agent
from evoconnect4.agent.genome import decode
from evoconnect4.game.connect_four import Board
from evoconnect4.game.match import MatchResult, play_match
from evoconnect4.storage.repository import Repository

DEFAULT_HUMAN_NAME = "Anonymous Human"

InputFn = Callable[[str], str]
PrintFn = Callable[[str], None]


class AgentSelectionError(Exception):
    pass


class QuitRequested(Exception):
    pass


# -- agent selection & reconstruction ----------------------------------------


def select_agent_record(repo: Repository, agent_selector: str) -> dict:
    try:
        agent_id = int(agent_selector)
    except ValueError:
        agent_id = None

    if agent_id is not None:
        record = repo.get_agent(agent_id)
        if record is None:
            raise AgentSelectionError(f"No agent found with id {agent_id}")
        return record

    if agent_selector == "best-alive":
        candidates = repo.list_agents(status="alive")
        if not candidates:
            raise AgentSelectionError("No alive agents found in this database")
        return max(candidates, key=lambda a: a["fitness"])

    if agent_selector == "best-ever":
        candidates = repo.list_agents()
        if not candidates:
            raise AgentSelectionError("No agents found in this database")
        return max(candidates, key=lambda a: a["fitness"])

    raise AgentSelectionError(
        f"Unrecognized --agent value {agent_selector!r}; expected an integer id, 'best-alive', or 'best-ever'"
    )


def load_agent(repo: Repository, agent_selector: str) -> Agent:
    record = select_agent_record(repo, agent_selector)

    sim_config = repo.get_simulation_config()
    if sim_config is None:
        raise AgentSelectionError("Database has no simulation_config record -- not a valid run database")

    genome = decode(
        {
            "weights": record["nn_weights"],
            "hidden_layer_sizes": record["nn_architecture"],
            "lifespan": record["lifespan"],
            "mutation_rate": record["mutation_rate"],
            "crossover_rate": record["crossover_rate"],
        }
    )
    return Agent(
        genome,
        sim_config["board_columns"],
        sim_config["board_rows"],
        agent_id=record["agent_id"],
        generation=record["generation"],
        parent1_id=record["parent1_id"],
        parent2_id=record["parent2_id"],
        parent_avg_fitness=record["parent_avg_fitness"],
    )


# -- board rendering & human input --------------------------------------------


def render_board(board: Board) -> str:
    symbols = {1: "X", -1: "O", 0: "."}
    lines = [
        " ".join(symbols[board.cell(c, r)] for c in range(board.columns))
        for r in range(board.rows - 1, -1, -1)
    ]
    lines.append(" ".join(str(c + 1) for c in range(board.columns)))
    return "\n".join(lines)


def make_human_chooser(*, input_fn: InputFn = input, print_fn: PrintFn = print) -> Callable[[Board], int]:
    def chooser(board: Board) -> int:
        print_fn(render_board(board))
        while True:
            raw = input_fn(f"Your move (1-{board.columns}), or 'quit': ").strip()
            if raw.lower() in ("quit", "q"):
                raise QuitRequested()
            try:
                column = int(raw) - 1
            except ValueError:
                print_fn("Invalid input -- enter a column number.")
                continue
            if column not in board.legal_moves():
                print_fn("Invalid move -- that column is out of range or full.")
                continue
            return column

    return chooser


def prompt_yes_no(question: str, *, input_fn: InputFn = input, print_fn: PrintFn = print) -> bool:
    while True:
        raw = input_fn(f"{question} [y/n]: ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print_fn("Please answer y or n.")


# -- single-game play loop -----------------------------------------------------


def _replay_final_board(move_history: list[int], first_mover: int) -> Board:
    """Reconstruct the final board position play_match ended with.

    play_match() always builds its own Board() internally and never returns
    it, so the final position is recovered by deterministically replaying
    the recorded move history from the same starting player -- Board.drop()
    is pure game logic, so this reproduces the exact same end state.
    """
    board = Board()
    board.current_player = first_mover
    for column in move_history:
        board.drop(column)
    return board


def _db_result(result: MatchResult) -> str:
    if result.winner == 1:
        return "player1_win"
    if result.winner == -1:
        return "player2_win"
    return "draw"


def report_result(result: MatchResult, *, print_fn: PrintFn = print) -> None:
    if result.winner == 1:
        print_fn("Agent wins!")
    elif result.winner == -1:
        print_fn("You win!")
    else:
        print_fn("It's a draw!")


def play_one_game(agent: Agent, *, input_fn: InputFn = input, print_fn: PrintFn = print) -> MatchResult:
    print_fn("You are 'O', the agent is 'X'.")
    human_first = prompt_yes_no("Do you want to move first?", input_fn=input_fn, print_fn=print_fn)
    first_mover = -1 if human_first else 1  # human is always chooser_b (board position -1)

    chooser = make_human_chooser(input_fn=input_fn, print_fn=print_fn)
    result = play_match(agent.choose_move, chooser, first_mover=first_mover)

    final_board = _replay_final_board(result.move_history, first_mover)
    print_fn(render_board(final_board))
    report_result(result, print_fn=print_fn)
    return result


# -- session loop & game logging ------------------------------------------------


def run_session(repo: Repository, agent: Agent, *, input_fn: InputFn = input, print_fn: PrintFn = print) -> None:
    name = input_fn(f"Your name? [{DEFAULT_HUMAN_NAME}]: ").strip() or DEFAULT_HUMAN_NAME
    state = repo.get_simulation_state()
    tick = state["current_tick"] if state is not None else 0

    while True:
        try:
            result = play_one_game(agent, input_fn=input_fn, print_fn=print_fn)
        except (QuitRequested, KeyboardInterrupt):
            print_fn("Goodbye.")
            return

        repo.insert_game(
            tick=tick,
            player1_agent_id=agent.agent_id,
            player2_agent_id=None,
            game_type="human_vs_agent",
            opponent_label=name,
            result=_db_result(result),
            num_moves=result.num_moves,
            move_history=result.move_history,
        )
        repo.commit()

        if not prompt_yes_no("Play again?", input_fn=input_fn, print_fn=print_fn):
            print_fn("Goodbye.")
            return


# -- CLI entry point -------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play a full game of Connect Four against a saved EvoConnect4 agent.")
    parser.add_argument("--db", type=str, required=True, help="Path to the run database to load the agent from")
    parser.add_argument("--agent", type=str, required=True, help="Agent id, 'best-alive', or 'best-ever'")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    repo = Repository(args.db)
    try:
        agent = load_agent(repo, args.agent)
        run_session(repo, agent)
    except AgentSelectionError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        repo.close()


if __name__ == "__main__":
    main()
