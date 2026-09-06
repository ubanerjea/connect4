# Phase 8 — Human-vs-Agent Interface

*A terminal CLI to play a full, correctly-ruled game against any saved agent. See `evoconnect4_project_plan.md` §11.*

This document is a self-contained brief for entering the OpenSpec propose/apply cycle. It assumes Phases 0-7 are already built and archived — in particular Phase 5's frozen `simulation_config` (board dimensions, read from the database, never from live `config.yaml`) and Phase 6's `games` table (nullable `player2_agent_id` + `opponent_label`, with `Repository.insert_game`'s validation already generic to any non-`'evolution'` `game_type`, `'human_vs_agent'` included). No open questions remain — every decision below was explicitly resolved in the design conversation that produced this document.

## Why

This is the last piece of plan §12's literal MVP Definition of Done: *"A human can run the CLI, load the current best agent, and play a full, correctly-ruled game against it."* `interface/` is still an empty Phase 0 stub package. Everything this phase needs — genome round-trip, a chooser-agnostic match runner, and a `games` schema already shaped for a human opponent — already exists from prior phases; this phase is primarily wiring, with one real correctness point (see Design) and a handful of UX decisions the plan text left open.

## Scope

**In scope:**
1. `interface/play_cli.py`: `--db <path> --agent <id | best-alive | best-ever>`.
2. Loading and reconstructing the chosen agent from storage, sourcing board dimensions (`board_columns`/`board_rows`) from the target database's frozen `simulation_config` — never from the live `config.yaml`.
3. A play loop, repeated as a "play again?" session: ask who moves first before each game, render the board as text, alternate turns (human via validated, 1-indexed column input; agent via `choose_move`), report the result, and log the game.
4. Prompting for the human's name once per session (default `"Anonymous Human"` if left blank), reused as `opponent_label` for every game played in that session.
5. Quit handling: an explicit quit input or `Ctrl+C`, at any prompt, exits cleanly without logging an in-progress game.

**Out of scope:**
- Human games counting toward agent fitness — plan §5/§8 explicitly exclude this; plan §13 already notes it as a deferred future extension (not this phase, not reopened here).
- A graphical board (`pygame`, a local web page) — plan §8 itself calls this "a natural stretch addition... but adds nothing functionally the CLI doesn't already cover." Not this phase.
- Any change to `Repository`, `schema.py`, `game/match.py`, or `game/bots.py` — everything this phase needs already exists.

## Design: agent selection & the board-dimension correctness point

```
IF --agent is an integer:
    record = repo.get_agent(int(--agent))          -- works for alive or dead agents
ELIF --agent == "best-alive":
    candidates = repo.list_agents(status="alive")
ELIF --agent == "best-ever":
    candidates = repo.list_agents()                 -- no status filter, dead included
    (for either "best-*" mode: record = max(candidates, key=lambda a: a["fitness"]))
ELSE:
    error: unrecognized --agent value

IF record is None (bad id) OR candidates is empty (no agents matching best-*):
    error out clearly -- do not proceed with a missing agent

sim_config = repo.get_simulation_config()
genome = Genome.decode({
    "weights": record["nn_weights"], "hidden_layer_sizes": record["nn_architecture"],
    "lifespan": record["lifespan"], "mutation_rate": record["mutation_rate"],
    "crossover_rate": record["crossover_rate"],
})
agent = Agent(genome, sim_config["board_columns"], sim_config["board_rows"], agent_id=record["agent_id"], ...)
```

*(Pseudocode — an outline, not implementation.)*

**Why `simulation_config`, not `config.yaml`**: `play_cli.py` is a standalone script with no live `Population`/`Config` to inherit dimensions from, and `config.yaml` may have drifted since the target database's population was created — exactly the drift Phase 5's frozen-config validation exists to catch on resume. `Network.__init__` raises `ValueError` on a genuine size mismatch (a loud failure), but a *coincidentally*-matching wrong `(columns, rows)` pair would reconstruct successfully while silently misreading the board — a much worse failure mode. Sourcing board dimensions from the database's own frozen record avoids the whole class of bug, not just its loud version.

## Design: the play loop

Reuses `game/match.py`'s `play_match(chooser_a, chooser_b, first_mover)` entirely unchanged — the agent is always `chooser_a` (board position `1`), the human is always `chooser_b` (board position `-1`), for every game in the session, regardless of who moves first that particular game (`first_mover` controls turn order only, not board-position identity — same separation evolution and benchmark games already rely on).

```
name = prompt("Your name? [Anonymous Human]: ") or "Anonymous Human"

LOOP:
    human_first = prompt_yes_no("Move first this game?")
    first_mover = -1 if human_first else 1        -- chooser_b (human) is board position -1

    board = Board(sim_config["board_columns"], sim_config["board_rows"])
    TRY:
        result = play_match(agent.choose_move, human_chooser, first_mover=first_mover)
    CATCH QuitRequested:
        print("Goodbye.")
        RETURN                                      -- no game logged

    render(board)                                    -- show the FINAL position; play_match
                                                       -- itself never renders after the last move
    report_result(result)                             -- "You win!" / "Agent wins!" / "Draw!"

    repo.insert_game(
        player1_agent_id=agent.agent_id, player2_agent_id=None,
        game_type="human_vs_agent", opponent_label=name,
        result=<mapped from result.winner>, num_moves=result.num_moves,
        move_history=result.move_history,
    )
    repo.commit()

    IF NOT prompt_yes_no("Play again?"): RETURN

def human_chooser(board) -> int:
    render(board)                                     -- board already reflects every move so
                                                        -- far, including the opponent's last one
    LOOP:
        raw = input("Your move (1-N), or 'quit': ")
        IF raw is a quit command: RAISE QuitRequested
        column = parsed 1-indexed input, translated to 0-indexed
        IF column is a legal move: RETURN column
        print("Invalid move, try again.")             -- re-prompt, do not crash or advance the board
```

*(Pseudocode — an outline, not implementation.)* `human_chooser` renders the board on every call, which — because it is only ever called on the human's own turn — always shows the position exactly as it stands after the opponent's most recent move, with zero extra rendering hooks needed in `match.py`. The one gap this leaves is the very last move of a game (if it ends the game, `play_match` returns immediately with no further render call), which is why the outer loop renders once more right after `play_match` returns, before reporting the result.

`Ctrl+C` (`KeyboardInterrupt`) is caught at the same point as an explicit quit command — treated identically: a clean goodbye message, no traceback, no `games` row written for that in-progress game.

## Definition of done

- Matches plan §12's literal MVP bullet: a human can run the CLI, load the current best agent, and play a full, correctly-ruled game against it, start to finish.
- All three `--agent` selection modes work (`<id>`, `best-alive`, `best-ever`), each erroring clearly rather than crashing when the requested agent/criterion doesn't resolve (bad id, empty population for `best-alive`).
- A test confirms board dimensions used for reconstruction come from the target database's `simulation_config`, independent of whatever `config.yaml` currently says (e.g., a deliberately different live `board_columns` doesn't affect `play_cli.py`'s reconstruction).
- A test confirms a completed game is logged with `game_type='human_vs_agent'`, `player2_agent_id=None`, and `opponent_label` equal to the entered (or default `"Anonymous Human"`) name — and that the agent's own `games_played`/`wins`/`losses`/`draws`/`fitness` are unchanged by it, the same non-interference guarantee Phase 6 already established for benchmark games.
- A test confirms quitting mid-game writes no `games` row.
- A test confirms invalid human input (out-of-range column, non-integer, a full column) re-prompts rather than crashing or corrupting the board.
- Full existing test suite continues to pass.

## Dependencies

Builds on Phase 3 (`Repository.get_agent`/`list_agents`), Phase 5 (frozen `simulation_config` for board dimensions), Phase 6 (`games`' generic non-evolution validation already covers `game_type='human_vs_agent'` with no further changes), `game/match.py` (chooser-agnostic `play_match`), and `agent/genome.py` (`decode`). No new external dependencies — stdlib `input()`/`print()` only, per plan §7's own stated choice for the human CLI.

## Known limitations

- ASCII board only, by explicit design — plan §8 itself frames a GUI as a stretch addition that adds nothing functional the CLI doesn't already cover.
- Human games never influence agent fitness — deliberately excluded; see plan §13's already-noted (not built) future extension for counting them.
- Single local terminal session only — no networked or remote play, consistent with this project's single-machine, single-process scope everywhere else.
