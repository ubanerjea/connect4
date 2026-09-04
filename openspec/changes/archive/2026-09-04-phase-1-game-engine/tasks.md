## 1. Board Core

- [x] 1.1 Implement `Board` with `columns`/`rows` constructor params (default 7/6) and an empty-grid initial state, and verify a unit test asserts a default board has 7 columns, 6 rows, and every cell empty
- [x] 1.2 Implement `legal_moves()` and `drop(column)` with gravity (piece settles to the lowest empty cell), mutating the board in place, and verify a unit test confirms pieces stack bottom-up within a column
- [x] 1.3 Implement illegal-move rejection — a full column and an out-of-range column both raise `ValueError` and leave board state unchanged — and verify unit tests cover both cases and assert the board is unmodified after each rejected attempt
- [x] 1.4 Implement turn alternation (current player toggles after each accepted move, not after a rejected one) and verify a unit test asserts this for both outcomes

## 2. Win & Draw Detection

- [x] 2.1 Implement incremental win detection from the just-placed cell across all 4 directions (horizontal, vertical, diagonal ascending, diagonal descending) and verify 4 unit tests, one per direction, each confirming the correct winner is reported
- [x] 2.2 Implement draw detection (board full, no winner) and verify a unit test fills a board with no four-in-a-row and asserts the game is reported as a draw, not ongoing

## 3. Deterministic Bots

- [x] 3.1 Implement `random_mover(board) -> int` choosing uniformly among legal columns and verify a unit test runs it repeatedly on a partially-filled board and asserts every returned column is legal
- [x] 3.2 Implement `heuristic_bot(board) -> int` taking an immediate winning move when one exists, and verify a unit test sets up a board with an available winning move and asserts it's chosen
- [x] 3.3 Extend `heuristic_bot` to block the opponent's immediate winning move when it has no win of its own, and verify a unit test sets up a board where only a block is available and asserts it's chosen
- [x] 3.4 Extend `heuristic_bot` to prefer center columns as a fallback (random tie-break) when no win or block is available, and verify a unit test on an empty board asserts a center (or tied-nearest-center) column is chosen

## 4. Match Runner

- [x] 4.1 Implement `play_match(chooser_a, chooser_b, first_mover)` that alternates turns and calls the appropriate chooser until a win or draw is reached, and verify a full match between `heuristic_bot` and `random_mover` completes and returns a terminal result
- [x] 4.2 Implement a match result carrying winner, move history, and move count, and verify a unit test asserts move-history length equals the move count and matches the moves actually played
- [x] 4.3 Verify the `first_mover` parameter controls which chooser moves first — a unit test using a spy/wrapper chooser asserts the first move in the history came from the designated first mover
- [x] 4.4 Verify `match.py` propagates a chooser's illegal move as a raised `ValueError` rather than handling it — a unit test asserts a chooser returning a full/out-of-range column raises

## 5. Full Suite Verification

- [x] 5.1 Verify `uv run pytest` passes across `tests/test_connect_four.py`, `tests/test_bots.py`, `tests/test_match.py`, and the existing Phase 0 tests with zero failures
- [x] 5.2 Verify plan §11's Phase 1 roadmap bar is met — unit tests cover all 4 win directions, draws, and illegal moves — by confirming each is present and passing in the suite from 5.1
