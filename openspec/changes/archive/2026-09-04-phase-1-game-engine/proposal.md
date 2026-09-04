## Why

EvoConnect4 has no game logic yet — Phase 0 scaffolded the project structure only. Every later phase (agent forward-passes, the evolutionary tick loop, the database, human play) depends on a working, correctly-ruled Connect Four engine to play against. Phase 1 of the plan's roadmap (§11) is exactly this: board, legal moves, and win/draw detection.

## What Changes

- Add a mutable `Board` class (`src/evoconnect4/game/connect_four.py`) implementing Connect Four rules from plan §2: 7×6 grid (configurable), gravity-drop moves, legal-move tracking, illegal-move rejection, and win detection in all 4 directions (horizontal, vertical, both diagonals) plus draw detection. Cells encode ownership as `+1` / `-1` per player, `0` empty — chosen so Phase 2's relative NN input encoding (plan §3.1) becomes a single sign multiply, no translation step.
- Add deterministic move-choosing bots (`src/evoconnect4/game/bots.py`): `random_mover` (uniform random legal column) and `heuristic_bot` (win-if-possible → block → prefer-center → random tie-break, per plan §5). These are plain functions (`Board -> int`), not agents — no neural network or genome involved. Scoped as pure game-logic; the scheduled-evaluation-against-population-best machinery described for baseline benchmarking in plan §11 Phase 6 is explicitly out of scope here.
- Add a match runner (`src/evoconnect4/game/match.py`) that plays one full game between two move-choosing callables (`Board -> int`) and returns a result (winner, move history, move count) — shaped to mirror the `games` table's fields (plan §6) without touching persistence, which doesn't exist until Phase 3.

## Capabilities

### New Capabilities
- `connect-four-game`: Playing a complete, correctly-ruled game of Connect Four end-to-end — board state and legal-move tracking, win/draw detection, illegal-move rejection, two example deterministic move-choosing strategies, and a runner that plays a full game between any two such strategies.

### Modified Capabilities

None.

## Impact

- New files: `src/evoconnect4/game/connect_four.py`, `src/evoconnect4/game/bots.py`, `src/evoconnect4/game/match.py`, `tests/test_connect_four.py`, `tests/test_bots.py`, `tests/test_match.py`.
- No new runtime dependencies (plain Python, per plan §7 — "Game logic: Plain Python... a dependency would be overkill").
- No changes to existing Phase 0 files (config, entry point, other placeholder subpackages untouched).
- This change is broader than plan §11's literal Phase 1 row ("board, legal moves, win/draw detection") — it also includes `bots.py` and `match.py`, pulled forward from later phases as pure logic with no structural dependencies (DB, population) attached. Plan §11's Phase 1 row is worth a follow-up one-line update once this is implemented, mirroring the §7 update made after Phase 0.
