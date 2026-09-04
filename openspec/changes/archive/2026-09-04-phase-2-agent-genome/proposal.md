## Why

EvoConnect4 has a working game engine (Phase 1) but no way yet for an evolvable neural network to actually choose moves. Phase 2 of the plan's roadmap (§11) builds that: a forward-pass network, a genome representation with random init and encode/decode, and — per the same "pull pure logic forward" call made for Phase 1's bots — the `mutate()`/`crossover()` operators themselves, since they're self-contained genome-to-genome functions with no dependency on the population machinery (tournament selection, reproduction timing) that Phase 4 actually owns.

## What Changes

- Add a pure-`numpy` feedforward network (`src/evoconnect4/agent/network.py`): builds from a flat weight vector into layer matrices, forward pass (`tanh` hidden layer(s), linear output), fully decoupled from the game engine — it operates on plain arrays, never imports `Board`. Input/hidden/output sizes derive from config (`board_columns * board_rows`, `hidden_layer_sizes`, `board_columns`), not hardcoded to 42/7.
- Add a `Genome` representation (`src/evoconnect4/agent/genome.py`): flat NN weight vector, `hidden_layer_sizes` (architecture reserved per plan §3.4, fixed at birth), `lifespan`, self-adaptive `mutation_rate` (σ), `crossover_rate`. Includes random initialization, encode/decode (genome ↔ a plain serializable form, for later DB storage in Phase 3), and the `mutate()` (Gaussian noise on weights scaled by σ, self-adaptive log-normal update to σ itself, multiplicative step on lifespan, additive step on crossover_rate — all per plan §3.2) and `crossover()` (uniform crossover on weights, average of trait genes, per plan §3.3) operators. Picking *which* second genome to cross with (tournament selection over a live population) remains Phase 4's responsibility — only the combine-two-genomes-into-one operation is built here.
- Add a minimal `Agent` wrapper (`src/evoconnect4/agent/agent.py`): wraps a genome + the network built from it, converts a `Board` to the network's relative-encoded input (own discs `+1`, opponent `-1`, empty `0`, per plan §3.1 — `board * board.current_player`, flattened), and exposes `choose_move(board) -> int`, satisfying Phase 1's `Chooser` protocol so a genome-driven agent can play via `match.py` immediately. No live-stats (games_played, wins, fitness) and no mutable live-weights for somatic mutation — both need context (a database, a running tick loop) that don't exist until Phase 3/4, and are explicitly deferred.
- Tighten `config.yaml`'s `lifespan_range` from `[30, 200]` to `[50, 150]` — narrows the "free lifespan" window described in the plan's new §4.7 until Phase 4 builds the actual senescence mitigation.

## Capabilities

### New Capabilities
- `agent-genome`: An evolvable agent — a neural-network genome that can be randomly initialized, serialized and restored, mutated, and combined with another genome via crossover, and realized into a network that chooses legal Connect Four moves.

### Modified Capabilities

None.

## Impact

- New files: `src/evoconnect4/agent/network.py`, `src/evoconnect4/agent/genome.py`, `src/evoconnect4/agent/agent.py`, `tests/test_network.py`, `tests/test_genome.py`, `tests/test_agent.py`.
- Modified files: `config.yaml` (`lifespan_range` tightened to `[50, 150]`).
- No new dependencies — `numpy` is already present from Phase 0.
- No changes to `src/evoconnect4/game/` (Phase 1) — `Agent.choose_move` consumes `Board` read-only via its existing public API (`legal_moves()`, `cell()`, `current_player`).
