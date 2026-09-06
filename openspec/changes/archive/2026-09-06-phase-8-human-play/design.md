## Context

`interface/` is still an empty Phase 0 stub package. Everything else this phase needs already exists: `Repository.get_agent`/`list_agents` (Phase 3), the frozen `simulation_config` record with `board_columns`/`board_rows` (Phase 5), `game/match.py`'s `play_match(chooser_a, chooser_b, first_mover)` which treats a "chooser" as any `Board -> int` callable — a human-input function satisfies this identically to a bot or an `Agent.choose_move` (Phase 1/2), and `Repository.insert_game`'s validation, already generic to any non-`'evolution'` `game_type` (Phase 6) — `'human_vs_agent'` needs no further storage-layer work. `Board`'s dimensions are Connect Four's own rules (plan §2: "Board: 7 columns × 6 rows"), not a supported axis of variation, despite being technically parameterized in `Config`/`Board` for engine-generality and testability reasons — so board-dimension sourcing here is about correctness against `config.yaml` drift (matching Phase 5's resume-validation reasoning), not about supporting arbitrary board sizes.

See proposal.md for motivation; see the delta spec for full behavioral requirements.

## Goals / Non-Goals

**Goals:**
- A human can load any saved agent (by id, best-alive, or best-ever) and play a full, correctly-ruled game against it from a terminal.
- Board dimensions used for reconstruction always match the target database's own recorded population, never a possibly-drifted live `config.yaml`.
- Human games are logged durably but never influence the agent's official evolutionary record.

**Non-Goals:**
- A graphical board (`pygame`, a local web page) — plan §8 itself frames this as a stretch addition that "adds nothing functionally the CLI doesn't already cover."
- Human games counting toward agent fitness — plan §5/§8 explicitly exclude this; plan §13 already notes it as a deferred future extension.
- Any change to `Repository`, `schema.py`, `game/match.py`, or `game/bots.py` — confirmed during this change's design conversation that everything needed already exists; `match.py`'s hardcoded 7×6 `Board()` is not a gap to close, since arbitrary board sizes were never a supported requirement (see Context).
- Networked or remote play — single local terminal session only, consistent with this project's single-machine scope everywhere else.

## Decisions

### Agent selection: three mutually exclusive `--agent` forms, resolved via existing `Repository` methods
`--agent <id>` → `repo.get_agent(int(id))`. `--agent best-alive` → `max(repo.list_agents(status="alive"), key=fitness)`. `--agent best-ever` → `max(repo.list_agents(), key=fitness)` (no status filter, dead agents included — deliberately, since a dead agent's final stats remain fully valid per plan §8's own note). Any unresolved selection (bad id, or a fitness-ranking mode over an empty candidate set) is a clear, immediate error — the CLI never falls back to a default agent silently.

### Board dimensions: read once from `simulation_config`, passed explicitly, never re-read from `config.yaml`
`play_cli.py` is a standalone script with no live `Population`/`Config` to inherit dimensions from. Using `load_config()` (the same helper `run_simulation.py` uses for genuinely-live config) would silently reintroduce exactly the config-drift risk Phase 5's frozen-config resume validation exists to prevent — except here there would be no validation step to catch it, since `play_cli.py` never touches `config.yaml` for anything else. Reading `board_columns`/`board_rows` from `repo.get_simulation_config()` avoids the class of bug entirely rather than needing to detect it after the fact.

### The play loop reuses `play_match()` unchanged; a human "chooser" renders on its own turn
The agent is always `chooser_a` (board position `1`), the human is always `chooser_b` (board position `-1`), for every game in a session, regardless of who moves first that particular game — `first_mover` controls turn order only, the same separation evolution and benchmark games already rely on. The human-input function renders the board every time it is called; since it is only ever called on the human's own turn, this always shows the position exactly as it stands after the opponent's most recent move, needing no new rendering hook in `match.py`. The one gap this leaves is the game's very last move: if it ends the game, `play_match` returns immediately with no further call to the human chooser, so nothing renders the final position. The play loop closes this gap by rendering once more, explicitly, right after `play_match` returns and before reporting the result.

### Quit is a control-flow exception, not a game outcome
`games.result` only has `'player1_win'`/`'player2_win'`/`'draw'` — there is no "incomplete" value, and none is added. An explicit quit command or `Ctrl+C` (`KeyboardInterrupt`) is caught at the play-loop level, both treated identically: a clean exit message, no traceback, and no `insert_game` call for that in-progress game. `repo.insert_game` is only ever reached after `play_match` returns a genuine result.

### The human's name is prompted once per session, reused across every game in the "play again?" loop
Asking for a name before every single game in a multi-game session would be needless friction; asking once and reusing it as `opponent_label` for each logged game in that session matches how a person would actually expect to use the CLI. Left blank, it defaults to `"Anonymous Human"`.

### Column input is 1-indexed for the human, translated internally
Displayed and typed columns are `1..N`; translated to the engine's `0..N-1` before being passed to `Board.drop()`/`legal_moves()` checks. This is a presentation-layer choice only — nothing below the input-parsing step in `play_cli.py` is aware of it.

## Risks / Trade-offs

- **No graphical board** → accepted; explicitly out of scope per plan §8's own framing, and the ASCII rendering already used for testing/debugging elsewhere in the project is sufficient for this phase's goal.
- **`play_match()`'s hardcoded 7×6 `Board()` remains unaddressed** → deliberately not fixed; investigated during this change's design conversation and concluded that arbitrary Connect Four board sizes are not a real requirement (plan §2 defines the board size as a game rule, not a tunable), so there is nothing to fix relative to what this project actually needs.
- **Session state is entirely in-memory, lost on crash** → acceptable; a human play session is short-lived and interactive by nature, unlike Phase 5's long-running headless simulations that specifically need pause/resume.

## Open Questions

None — every decision above was resolved during the design conversation that produced `plans/phase-8-human-play.md` and this change's own propose-time discussion (agent-selection error handling, and the explicit decision not to touch `game/match.py`).
