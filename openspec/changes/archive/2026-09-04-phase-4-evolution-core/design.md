## Context

Everything this change needs already exists: Phase 1's `Board`/`play_match`, Phase 2's `Agent`/`Genome` (including `mutate()`/`crossover()`, pulled forward), and Phase 3's `Repository`. Nothing has driven them together yet. See proposal.md - Why, and the exploration that preceded this change (Agent extends directly with live-stats; senescence deferred to the newly added Phase 9).

## Goals / Non-Goals

**Goals:**
- Implement §4.2's tick loop faithfully, including §4.3 (reproduction timing), §4.4 (death), §4.5 (population cap).
- Satisfy §11's Phase 4 DoD: a 50-tick run on a small population shows plausible births/deaths, no runaway size.

**Non-Goals:**
- The benchmark-tick step in §4.2's pseudocode — Phase 6 owns scheduled evaluation against fixed baselines.
- Senescence (§4.7) — deferred to the newly added Phase 9.
- Resuming a population from an existing database — this change only creates and runs a fresh population; reload/resume is unbuilt and out of scope.
- Wiring this into `run_simulation.py` or a CLI — that's Phase 5.

## Decisions

**`Agent` is extended directly with live-stats** (`games_played`, `wins`, `losses`, `draws`, `fitness`, `games_since_last_reproduction`), not wrapped in a separate object. Decided in exploration: these fields are already game-agnostic (population/evolution bookkeeping, not game-specific), so a wrapper split wouldn't help future game-portability — the actual game-swap seam is `Board`/`Chooser`/`Agent._encode`, already isolated.

**Culling is checked after each reproduction event, not once at the end of the tick.** §4.2's pseudocode shows population-cap checking as one step after the whole reproduction loop, but §4.2 is explicitly captioned "an outline of the algorithm, not implementation." §4.5's prose is more precise: *"whenever a reproduction event would push the population over that cap"* — tied to each individual event, not a single end-of-tick check. Implementing it that way means the population is never observed to exceed capacity even transiently within a tick, which is the more defensible reading of §4.5 and still satisfies §4.2's intent.

**Match-to-database result mapping relies on `play_match`'s actual semantics, not just its signature.** `play_match(chooser_a, chooser_b, first_mover)` always assigns `chooser_a` to sign `+1` and `chooser_b` to sign `-1` — `first_mover` only sets which sign moves first, it does not swap the chooser-to-sign assignment. So across a pair's two games, the same population agent stays `player1`/`chooser_a` for both calls; only `first_mover` flips between them (`+1` then `-1`). This means `winner == 1` always maps to `player1_win`, `winner == -1` to `player2_win`, with no bookkeeping needed to track which agent "was" which sign per game.

**New agents born this tick do not play until the next tick.** Follows directly from §4.2's pseudocode ordering: `alive` is snapshotted at the start of the tick, before any reproduction happens; children are appended to the live pool but not to that tick's already-formed pairing list.

**A single `np.random.Generator`, seeded from `config.random_seed`, drives all randomness** (shuffling, odd-one-out, tournament sampling, and passed through to `genome.random_genome`/`mutate`/`crossover`) — consistent with how Phase 2's genome operators already accept an explicit `rng`, and needed for the 50-tick DoD test to be reproducible.

**Tournament selection excludes the reproducing agent itself**, sampling up to `min(tournament_size, len(alive) - 1)` other live agents without replacement and taking the fittest. Plan §3.3 says "pick a second parent" — read as implying a distinct second individual, the conventional model for sexual reproduction, and this avoids a degenerate (if harmless) self-crossover case entirely. The `min(...)` guard keeps this safe on populations smaller than `tournament_size` (relevant for tests).

**`offspring_count` is not actively maintained by this change.** §6's own schema notes describe it as *"a lineage stat, free to compute"* — read as: derivable later via a query over `parent1_id`/`parent2_id`, not a running counter this change needs to keep in sync. Avoids adding a new `Repository` method for a field the schema itself frames as computable on demand; new agents are inserted with it at `0`.

**Commit batching: one `repo.commit()` per tick**, not per insert/update — exactly what Phase 3's `Repository` was designed to support (§6's batch-commit note), now with a real caller.

**`Population` holds the live pool in memory**; `Repository` calls are one-way writes reflecting what happens, not a source Population re-reads from mid-run. Consistent with the Non-Goal above (no resume-from-DB in this change).

## Risks / Trade-offs

- [Culling-per-event vs. culling-once-per-tick is an interpretation call, since §4.2's pseudocode and §4.5's prose don't literally agree] → Accepted; documented above, and either reading satisfies the DoD's "no runaway size" bar in practice.
- [`offspring_count` staying at `0` means it's not yet a useful lineage stat until something computes it from parent links] → Accepted; matches the schema's own framing, and Phase 7 (analytics) is the natural place to compute it if/when needed.
- [Excluding self from tournament selection is a judgment call the plan doesn't state explicitly] → Accepted; low-risk either way (self-crossover degenerates to a clone), and this is the more conventional reading.
