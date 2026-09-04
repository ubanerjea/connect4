## Context

No game logic exists yet — `src/evoconnect4/game/` is an empty placeholder from Phase 0. This is the first module with real, testable behavior, and it's the foundation every later phase (agent forward-pass, evolution tick loop, database, human CLI) plays against. See proposal.md - Why.

## Goals / Non-Goals

**Goals:**
- A board representation and API shape that later phases (especially Phase 4's evolution loop, running hundreds of games per tick) can use without a rewrite.
- A move-choosing interface general enough that Phase 2's real NN-driven Agents plug into `match.py` with zero changes to `match.py` itself.

**Non-Goals:**
- Any persistence — `match.py`'s result is shaped like the future `games` table (plan §6) but nothing is written to a database; that's Phase 3.
- The scheduled-benchmarking apparatus (evaluating against the population's current-best agent, writing to `benchmark_results`, run on a tick schedule) — plan §11 scopes that to Phase 6. This change only builds the two bots' pure decision logic.
- Structural NN concerns (relative board encoding for a network's input layer) — that's Phase 2. This design picks a cell-encoding convention that makes Phase 2 easier, but doesn't implement it.

## Decisions

**Mutable `Board` class, not an immutable/functional board.** `board.drop(column)` mutates in place. Considered a functional `apply_move(board, column, player) -> new_board` instead, which is easier to reason about in isolation and trivial to snapshot/replay. Rejected because Phase 4's evolution loop plays hundreds of games per tick — copying the full board on every move adds real, avoidable cost at that scale, and there's no correctness benefit here since games are always played move-by-move in sequence, never branched or replayed mid-game.

**Cell values are `+1` (player A) / `-1` (player B) / `0` (empty), not `0`/`1`/`2` player IDs.** This makes Phase 3.1's relative NN encoding (own discs `+1`, opponent `-1`) a single elementwise sign multiply — `board * current_player_sign` — with no translation step in the agent module. The alternative (integer player IDs) reads slightly more conventionally but pushes a translation step into Phase 2 for no offsetting benefit.

**Win detection checks incrementally from the just-placed cell, not a full-board rescan.** After each `drop`, only the 4 lines passing through the new piece (horizontal, vertical, both diagonals) are checked. Cheaper than rescanning all 69 possible four-in-a-row windows on every move, and no more complex to implement — the check only needs the last move's coordinates, which `drop` already has.

**`bots.py` holds the two deterministic strategies, not `evolution/benchmarks.py`.** The proposal's scope note explains why: plan §11 names `evolution/benchmarks.py` as a Phase 6 deliverable that also owns scheduled evaluation and `benchmark_results` writes, neither of which exist yet. Placing the pure decision functions in `game/` keeps this change self-contained; Phase 6 imports them rather than reimplementing them.

**Move-choosing strategies are plain callables (`Board -> int`), not a class hierarchy.** `match.py` takes any two things callable as `Board -> int` — today, bare functions (`random_mover`, `heuristic_bot`); later, a bound method on a real `Agent`. This means `match.py` needs zero changes when Phase 2 introduces real agents — it never needed to know what a "chooser" is beyond its call signature.

**`match.py` does not catch a chooser returning an illegal column.** `Board.drop` raises `ValueError` on an illegal move; `match.py` lets it propagate rather than catching and forfeiting. A chooser returning an illegal move is a bug in that chooser (including, later, a buggy Agent), not a game state `match.py` should paper over.

**`Board` takes `columns`/`rows` as constructor parameters (default 7/6), and does not import the config module.** Keeps the game engine dependency-free, per plan §7's "Game logic: Plain Python... a dependency would be overkill." `config.yaml`'s `board_columns`/`board_rows` values get passed in explicitly by whatever later code constructs a `Board` (e.g., a future `population.py`), not read directly by the engine itself.

## Risks / Trade-offs

- [Mutable board state makes tests slightly more careful to write — a test must construct a fresh `Board` rather than reuse one] → Accepted; the performance benefit at Phase 4's scale outweighs this, and pytest fixtures make "fresh board per test" a non-issue in practice.
- [`bots.py` living in `game/` means Phase 6 will need to import across from `evolution/` back into `game/`] → Accepted; this is a normal import direction (evolution logic depending on game logic) and avoids duplicating the decision logic later.
- [This change is broader than plan §11's literal Phase 1 row] → Flagged in proposal.md's Impact section as a follow-up plan-doc update, mirroring the §7 update made after Phase 0.
