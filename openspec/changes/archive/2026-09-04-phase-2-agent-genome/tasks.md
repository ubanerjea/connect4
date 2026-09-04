## 1. Config

- [x] 1.1 Tighten `lifespan_range` in `config.yaml` from `[30, 200]` to `[50, 150]`, and verify the existing config-loader test suite still passes with the new bounds

## 2. Network

- [x] 2.1 Implement `Network` building from a flat weight vector into layer matrices (`W1`, `b1`, `W2`, `b2`) given input/hidden/output sizes, and verify a unit test asserts correct matrix shapes for known sizes
- [x] 2.2 Implement the forward pass (`tanh` hidden layer, linear output layer), and verify a unit test with a small, hand-computed weight vector produces the expected output values
- [x] 2.3 Implement flattening the network's matrices back into a single vector, and verify a round-trip unit test: a random weight vector built into a `Network` and flattened back out is identical to the original

## 3. Genome

- [x] 3.1 Implement the `Genome` representation (weights, `hidden_layer_sizes`, lifespan, mutation rate, crossover rate), and verify a unit test constructs one directly and reads every field back correctly
- [x] 3.2 Implement random genome initialization matching a configured architecture (weight count correct, weights `~N(0, weight_init_std²)`, biases zero, trait genes within their configured ranges), and verify unit tests for both the weight count and each trait gene's bounds
- [x] 3.3 Implement genome encode/decode (to/from a plain serializable form), and verify a round-trip unit test: decoding an encoded genome reproduces the original's weight vector, architecture, lifespan, mutation rate, and crossover rate
- [x] 3.4 Implement `mutate(genome) -> Genome` (weight Gaussian noise via a reusable helper, self-adaptive σ log-normal update, lifespan multiplicative step, crossover-rate additive step, all clamped to their configured ranges), and verify unit tests confirming the parent genome is left unchanged and the child's trait genes stay within bounds
- [x] 3.5 Implement `crossover(genome_a, genome_b) -> Genome` (uniform per-weight inheritance, trait genes averaged), and verify unit tests confirming each child weight matches one parent's corresponding weight and each trait gene equals the parents' average

## 4. Agent

- [x] 4.1 Implement `Agent(genome, columns, rows)`, building its `Network` from the genome's weights and architecture, and verify a unit test constructs an `Agent` from a random genome without error
- [x] 4.2 Implement board-to-input encoding (relative to the board's current player) and `choose_move(board) -> int`, and verify a unit test asserts the chosen move is always among `board.legal_moves()` across several board states
- [x] 4.3 Verify move choice is independent of player identity — a unit test constructs two boards that are mirror images of each other from each player's own perspective and asserts the same agent chooses the same column in both
- [x] 4.4 Verify an `Agent` can play a full match via Phase 1's `play_match()` unchanged — a test runs `play_match(agent.choose_move, random_mover)` and asserts it completes with a terminal result

## 5. Full Suite Verification

- [x] 5.1 Verify `uv run pytest` passes across `tests/test_network.py`, `tests/test_genome.py`, `tests/test_agent.py`, and all existing Phase 0/1 tests with zero failures
- [x] 5.2 Verify plan §11's Phase 2 roadmap bar is met — a round-trip test showing genome → network → identical weight vector back — is present and passing in the suite from 5.1
