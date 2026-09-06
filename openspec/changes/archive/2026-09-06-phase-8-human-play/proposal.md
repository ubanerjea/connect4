## Why

This is the last piece of plan §12's literal MVP Definition of Done: a human must be able to run a CLI, load the current best agent, and play a full, correctly-ruled game against it. `interface/` is still an empty Phase 0 stub package, even though everything this phase needs — genome round-trip, a chooser-agnostic match runner, and a `games` schema already shaped for a human opponent (Phase 6) — already exists.

## What Changes

- Add `interface/play_cli.py`: `--db <path> --agent <id | best-alive | best-ever>`.
- Load and reconstruct the chosen agent from storage, sourcing board dimensions (`board_columns`/`board_rows`) from the target database's frozen `simulation_config` — never from the live `config.yaml`, avoiding the drift Phase 5's frozen-config validation exists to prevent on resume.
- A play loop, repeated as a "play again?" session: ask who moves first before each game, render the board as text, alternate turns (human via validated, 1-indexed column input; agent via `choose_move`), report the result, and log the game (`game_type='human_vs_agent'`, `player2_agent_id=None`, `opponent_label` = the human's name, prompted once per session, defaulting to `"Anonymous Human"`).
- Quit handling: an explicit quit input or `Ctrl+C`, at any prompt, exits cleanly without logging an in-progress game.

## Capabilities

### New Capabilities
- `human-play-interface`: the terminal CLI for loading a saved agent and playing full, correctly-ruled games against it, with results logged as `human_vs_agent` games.

### Modified Capabilities
(none — `Repository`, `schema.py`, `game/match.py`, and `game/bots.py` are all unchanged. Phase 6's `insert_game` validation is already generic to any non-`'evolution'` `game_type`, so `'human_vs_agent'` needs no further storage-layer work.)

## Impact

- `src/evoconnect4/interface/play_cli.py` — new: agent selection/reconstruction, the play loop, board rendering, human move input, game logging.
- No changes to `src/evoconnect4/storage/repository.py`, `schema.py`, `game/match.py`, `game/bots.py`, or `evolution/population.py`.
- No new external dependencies — stdlib `input()`/`print()` only, per plan §7's own stated choice for the human CLI.
