## 1. Agent selection & reconstruction

- [x] 1.1 In new `src/evoconnect4/interface/play_cli.py`, implement `argparse` (`--db`, `--agent`) and agent selection for all three `--agent` forms (`<id>`, `best-alive`, `best-ever`) via `Repository.get_agent`/`list_agents`, raising a clear, immediate error (not crashing or falling back silently) when unresolved. Verify with tests covering all three selection modes plus the two failure cases (a nonexistent id; an empty candidate set for `best-alive`/`best-ever`).
- [x] 1.2 Implement agent reconstruction (`Genome.decode` + `Agent(...)`) using `repo.get_simulation_config()`'s `board_columns`/`board_rows` — never `load_config()`/a live `Config`. Verify with a test that uses a deliberately different live config value for board dimensions and confirms reconstruction still matches the target database's own recorded dimensions.

## 2. Board rendering & human input

- [x] 2.1 Implement text board rendering and a human move-input function with 1-indexed display/entry (translated to 0-indexed internally), validated against `board.legal_moves()`, re-prompting on invalid input (non-integer, out of range, a full column) without crashing or advancing the board. Accept an injectable input source (defaulting to `input`) so tests can supply canned responses. Verify with tests covering invalid-then-valid input sequences for each invalid case.
- [x] 2.2 Implement quit handling: an explicit quit command from the human input function raises a dedicated exception; `Ctrl+C` (`KeyboardInterrupt`) is caught identically at the play-loop level — both result in a clean exit message and no `games` row written. Verify with a test that quitting mid-game (via the injectable input source) exits cleanly with no `insert_game` call.

## 3. Single-game play loop

- [x] 3.1 Implement the per-game flow: ask who moves first, run `play_match(agent.choose_move, human_chooser, first_mover=...)` with the agent always as `chooser_a` and the human always as `chooser_b`, render the final board position once more after `play_match` returns (closing the gap left by `play_match` never rendering after the game-ending move), and report the result. Verify with a test that scripts a full game via canned human inputs and confirms correct win/draw detection and reporting for at least one win case and one draw case.

## 4. Session loop & game logging

- [x] 4.1 Implement the session-level loop: prompt for the human's name once per session (default `"Anonymous Human"` if left blank), and after each completed game, call `repo.insert_game(game_type="human_vs_agent", player2_agent_id=None, opponent_label=<name>, result=..., num_moves=..., move_history=...)` followed by `repo.commit()`, then ask "play again?" and repeat with the same loaded agent if yes. Verify with tests confirming: a completed game is logged with the correct `game_type`/`opponent_label`/`result`/`move_history`; the agent's own `games_played`/`wins`/`losses`/`draws`/`fitness` are unchanged after one or more human games; declining "play again?" ends the session without starting another game.
- [x] 4.2 Wire `main()` and a `argparse`-driven CLI entry point (`if __name__ == "__main__":`), matching the pattern already used by `run_simulation.py`/`analytics/plots.py`/`analytics/catalog.py`.

## 5. Full-suite verification

- [x] 5.1 Run the full existing test suite (`pytest`) and verify it still passes unchanged, confirming no regression to Phases 0-7.
