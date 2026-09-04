## Context

Phase 1 established `Board` (mutable, `+1`/`-1`/`0` cells, `current_player`, `legal_moves()`) and the `Chooser = Callable[[Board], int]` protocol that `match.py` plays against. Phase 0's `config.yaml` already carries every tunable this change needs: `weight_init_std`, `hidden_layer_sizes`, `lifespan_range`, `mutation_rate_range`, `mutation_rate_tau`, `crossover_rate_range`, `crossover_rate_mutation_std`. See proposal.md - Why for the scope decision (mutate/crossover pulled forward, mirroring Phase 1's bots.py precedent).

## Goals / Non-Goals

**Goals:**
- A network/genome pair whose round-trip fidelity is verifiable (§11's literal Phase 2 DoD).
- `mutate()`/`crossover()` as pure, self-contained genome-to-genome operators, reusable unchanged by Phase 4.
- An `Agent` that can play a real game via Phase 1's `match.py` today, with no changes to `match.py` itself.

**Non-Goals:**
- Tournament selection or reproduction timing (§3.3, §4.3) — needs a live population, which doesn't exist until Phase 4.
- Live-stats (games_played, wins, fitness) — needs the database (Phase 3) or the tick loop (Phase 4) to have any meaning.
- Somatic mutation / senescence (plan §4.7, newly added) — explicitly deferred to Phase 4; `Agent` here has no mutable live-weight state.
- Structural mutation of network architecture (§3.4/§13) — architecture is fixed at birth, as the MVP already specifies.

## Decisions

**`Network` stays fully decoupled from `Board`.** `Network.forward(input_vector) -> scores` takes and returns plain `numpy` arrays; it never imports `evoconnect4.game`. The board-to-input conversion (`board * board.current_player`, flattened) lives in `Agent`. Considered having `Network.forward(board)` accept a `Board` directly — rejected because it couples the core numeric code to the game engine for no benefit, and mirrors the same boundary already drawn for `match.py`'s choosers (Phase 1 design.md).

**Weight layout: `[W1.flatten(), b1, W2.flatten(), b2]`, concatenated in that order.** `Network` owns both directions: building from a genome's flat vector (reshape into matrices — "decode" in the DoD's sense) and flattening its matrices back out (used only by the round-trip test). Input size is `board_columns * board_rows`, output size is `board_columns`, hidden size(s) come from `hidden_layer_sizes` — none of these are hardcoded to 42/7, consistent with `Board`'s own configurability.

**Biases initialize to zero; weights initialize `~N(0, weight_init_std²)`.** Standard practice — zero biases add no asymmetry before any signal exists, and per-neuron weight randomness alone is enough to make hidden units behave differently from each other. Considered randomizing biases too; rejected as adding noise with no offsetting benefit.

**Genome's "encode/decode" (§11's wording) means genome ↔ a plain serializable form (dict), not the network's weight-vector reshape.** That reshape is `Network`'s job (see above). Genome's encode/decode exists for Phase 3's future DB storage (`agents.nn_weights`, plan §6) — there's no consumer yet, but it's cheap, self-contained, and explicitly named in §11's Phase 2 DoD.

**`mutate()` factors out a reusable "add Gaussian noise to a weight vector, scaled by σ" helper internally**, rather than being one monolithic function. Costs nothing now; plan §4.7's future somatic-mutation mechanism (Phase 4) will want to apply the identical math to a live weight copy instead of producing a new genome, and can reuse this helper unchanged. `mutate()` itself covers: weights (Gaussian noise scaled by the genome's own σ), the self-adaptive update `σ' = σ · e^{N(0, τ²)}` (clamped to `mutation_rate_range`, using `mutation_rate_tau`), lifespan (multiplicative Gaussian step, `lifespan_mutation_scale`, clamped to `lifespan_range`), and crossover_rate (additive Gaussian step, `crossover_rate_mutation_std`, clamped to `crossover_rate_range`) — all per plan §3.2. It returns a new `Genome`; the parent is never mutated in place.

**`crossover(genome_a, genome_b)` takes two already-chosen genomes and returns one child** — uniform per-weight coin-flip inheritance, trait genes averaged (plan §3.3, step 1's "combine" only). It does not perform tournament selection; *choosing* `genome_b` from a live population is Phase 4's job, layered on top of this operator unchanged.

**`lifespan_range` tightens from `[30, 200]` to `[50, 150]` in `config.yaml`.** Floor of 50 guarantees at least 2 reproduction chances even at the worst-case interval (25 games, §4.3). Ceiling of 150 shrinks the "free lifespan" window described in the plan's new §4.7 until Phase 4 actually builds the senescence mitigation. Random initial lifespan is sampled uniformly across this same (now-tightened) range — no separate, narrower init-only window, per the scope decided in conversation.

## Risks / Trade-offs

- [Pulling `mutate()`/`crossover()` forward means Phase 4 must integrate with this exact operator contract rather than designing it fresh] → Accepted; same trade-off already made for Phase 1's `bots.py`/`match.py`, and the contract (pure genome(s) in, genome out) is unlikely to need to change shape later.
- [Genome's dict encode/decode has no real consumer until Phase 3's DB exists] → Accepted; it's cheap, self-contained, and directly named in §11's Phase 2 DoD wording.
- [Tightening `lifespan_range` narrows genetic diversity in that trait relative to the original plan, before senescence exists to make a wider range safe] → Accepted as a deliberate, temporary mitigation; worth revisiting once Phase 4 builds §4.7's senescence design.
