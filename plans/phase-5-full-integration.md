# Phase 5 — Full Integration: Run Lifecycle & Config Persistence

*Wiring `run_simulation.py` into a real entry point, plus the run-lifecycle design (fresh starts, pause/resume, seed handling, config snapshotting) the plan never pinned down. See `evoconnect4_project_plan.md` §11.*

This document is a self-contained brief for entering the OpenSpec propose/apply cycle. It assumes Phases 0-4b are already built and archived, in particular Phase 4b's `Agent.parent1_id`/`parent2_id` fields (reused here, not re-added). No open questions remain — every decision below was explicitly resolved in the design conversation that produced this document.

## Why

Everything needed to run a real simulation exists after Phase 4b — a game engine, evolvable agents, storage, and a working tick loop. `run_simulation.py` is still the Phase 0 stub (loads config, imports subpackages, prints settings, exits). Wiring it into a real entry point surfaces three questions the plan never answered, because they only make sense once there's something to actually *invoke*: how long does one run last, what happens to the database across repeated invocations, and how much reproducibility does a resumed run actually get.

## Scope

**In scope:**
1. CLI arguments on `run_simulation.py`: `--ticks`, `--seed`, `--db`.
2. Fresh-vs-resume decision logic, based on the target `--db` path's existing content.
3. Three new pieces of storage: `simulation_config` (frozen), `simulation_config_history` (mutable), `simulation_state` (execution state).
4. `Population.load(config, repo)` — the resume counterpart to the existing `initialize()`.
5. Resume-time validation of frozen config fields, with a hard refusal (not a warning) on mismatch.
6. RNG-state persistence for exact bit-for-bit resume continuity, with an explicit override path for deliberately branching to a new seed at resume time.

**Out of scope:**
- Any change to tick-loop evolutionary mechanics — that's Phase 4b, assumed already landed.
- Config-value versioning or migration beyond the frozen/mutable split — an unclassified new config field defaults to frozen (fail-safe: must match exactly, or resume is refused), full stop. No auto-migration mechanism.
- Multi-machine or concurrent-writer database access — still a single SQLite file, single process, per plan §6.
- Benchmark-tick scheduling (Phase 6) and the CLI human-play interface (Phase 8) — unrelated concerns.

## Core principle: one database file = one population's continuous lifetime

A file is never shared between two *unrelated* populations. Starting a new population always requires a fresh (nonexistent, or empty-of-live-agents) path. Resuming means pointing at an existing path that already contains a live population — the same population, continuing.

```
                    +-------------------------+
                    |   target --db path       |
                    +-------------------------+
                               |
                 does it exist AND have a
                 live population in it?
                    /                    \
                  NO                     YES
                   |                       |
                   v                       v
           +----------------+     +------------------+
           |  FRESH START   |     |     RESUME       |
           +----------------+     +------------------+
           | Population     |     | validate frozen  |
           |  .initialize() |     |  config matches  |
           | seed = --seed  |     |  simulation_      |
           | flag, else     |     |  config snapshot  |
           | config.yaml's  |     | Population.load() |
           | random_seed    |     | continue tick     |
           +----------------+     | count from        |
                                   | simulation_state  |
                                   +------------------+
                                          |
                                 --seed given at resume?
                                  /            \
                                NO             YES
                                 |               |
                                 v               v
                        restore EXACT      branch off a NEW
                        persisted RNG      rng seeded with
                        state (bit-for-  the given value --
                        bit continuation)  deliberately diverge
                                          from here forward
```

Rerunning fresh with the same or a different seed falls out of this for free: it's a normal fresh start at a *new* file path (auto-timestamped by default unless `--db` names an explicit path), with `--seed` choosing which value governs that new, independent population.

## CLI arguments

| Argument | Default | Purpose |
|---|---|---|
| `--ticks` | `500` | Number of ticks to run *this invocation* (not a config.yaml tunable — it's a per-invocation choice, not a property of the population itself) |
| `--seed` | none (fresh: falls back to `config.yaml`'s `random_seed`; resume: falls back to preserving persisted RNG state) | Overrides the seed. See the fresh/resume flow above for exact semantics. |
| `--db` | auto-generated timestamped path, e.g. `data/evoconnect4_<YYYYMMDD_HHMMSS>.db` | Target database file. An existing path with a live population triggers resume; anything else triggers a fresh start at that path. |

## Why reproducibility matters (context for whoever picks this up)

Worth stating plainly since it shaped several design choices below: holding the seed constant across two runs isn't about learning something new from re-running — it's about isolating the effect of something *else* you changed (a config tweak, a code refactor) from the effect of randomness. Re-running with a fixed seed and a changed config is a controlled comparison; re-running with a different seed is a deliberate way to sample the space of possible outcomes instead. Both are useful, for different purposes — the CLI supports both without requiring an edit to `config.yaml` for either.

## New storage: three tables, three different lifecycles

```
+---------------------------------------------------------------------+
|  simulation_config  (frozen, single row, written once)               |
+---------------------------------------------------------------------+
|  board_columns, board_rows, hidden_layer_sizes, weight_init_std,     |
|  + any future config field not explicitly in the mutable allowlist   |
|  below (fail-safe default: unclassified = frozen)                    |
|                                                                       |
|  Written once, at population creation. Validated (exact match)       |
|  against the live config.yaml on every resume attempt -- mismatch    |
|  refuses the resume with a clear error naming the field(s).           |
+---------------------------------------------------------------------+

+---------------------------------------------------------------------+
|  simulation_config_history  (mutable, append-only, one row per       |
|  "this config became effective starting at this tick" event)         |
+---------------------------------------------------------------------+
|  tick, population_size, lifespan_range, lifespan_mutation_scale,     |
|  mutation_rate_range, mutation_rate_tau, crossover_rate_range,       |
|  crossover_rate_mutation_std, tournament_size,                       |
|  reproduction_interval_min/_max, games_per_pair_per_tick,            |
|  benchmark_every_n_ticks, benchmark_games_per_opponent,               |
|  random_seed, cull_fraction_range, cull_fraction_beta_a,             |
|  cull_fraction_beta_b, cull_allow_immature_offspring                  |
|                                                                       |
|  First row at tick=0 (the initial config). A new row is appended     |
|  only when a resume finds any of these values changed from the       |
|  most recent row. "What was tournament_size at tick 250?" is         |
|  `SELECT ... WHERE tick <= 250 ORDER BY tick DESC LIMIT 1`.           |
+---------------------------------------------------------------------+

+---------------------------------------------------------------------+
|  simulation_state  (current execution state, single row, always      |
|  overwritten -- NOT a config record, purely mechanical)              |
+---------------------------------------------------------------------+
|  rng_state (opaque bit-generator continuation blob, JSON-serialized  |
|  numpy Generator.bit_generator.state), current_tick                  |
+---------------------------------------------------------------------+
```

Two deliberate separations: `random_seed` lives in the *history* table (a human-meaningful, tick-stamped fact worth querying), while the actual `rng_state` bytes live in `simulation_state` instead (opaque continuation data, never worth inspecting or comparing across runs). The frozen table is written once, ever; the history table is genuinely append-only and grows only when a resume actually changes something.

## Config classification (the allowlist)

**Mutable/live** — belongs in `simulation_config_history`, may legitimately differ across a resume, re-read fresh from `Config` on every use (never baked into stored per-agent data):

`population_size`, `lifespan_range`, `lifespan_mutation_scale`, `mutation_rate_range`, `mutation_rate_tau`, `crossover_rate_range`, `crossover_rate_mutation_std`, `tournament_size`, `reproduction_interval_min`, `reproduction_interval_max`, `games_per_pair_per_tick`, `benchmark_every_n_ticks`, `benchmark_games_per_opponent`, `random_seed`, `cull_fraction_range`, `cull_fraction_beta_a`, `cull_fraction_beta_b`, `cull_allow_immature_offspring` (the last four from Phase 4b).

**Frozen** — belongs in `simulation_config`, validated for exact match at every resume, and — critically — this is the *default* for anything not explicitly listed above:

`board_columns`, `board_rows` (baked into every existing agent's `Network` shape via its stored flat weight vector's fixed length — changing these would make existing agents unreconstructable), `hidden_layer_sizes`, `weight_init_std` (both only ever consulted once, at generation-0 `random_genome()` calls — never re-read afterward in the current design, but frozen anyway since nothing would benefit from letting them drift, and `hidden_layer_sizes` specifically must stay consistent across the whole population for `crossover()`'s per-weight mask to remain shape-compatible between any two agents).

Any future config field added later and not explicitly placed in the mutable list above is frozen by default — a fail-safe stance, not a fail-open one.

## `Population.load(config, repo)`

The resume counterpart to `initialize()`. Reconstructs a live population entirely from already-existing round-trip machinery — nothing here is new plumbing beyond gluing it together:

```
FUNCTION load(config, repo):
    population = Population(config, repo)
    FOR record in repo.list_agents(status="alive"):
        genome = Genome.decode({
            "weights": record["nn_weights"],
            "hidden_layer_sizes": record["nn_architecture"],
            "lifespan": record["lifespan"],
            "mutation_rate": record["mutation_rate"],
            "crossover_rate": record["crossover_rate"],
        })
        agent = Agent(
            genome, config.board_columns, config.board_rows,
            agent_id=record["agent_id"],
            generation=record["generation"],
            parent1_id=record["parent1_id"],
            parent2_id=record["parent2_id"],
        )
        agent.games_played = record["games_played"]
        agent.wins = record["wins"]
        agent.losses = record["losses"]
        agent.draws = record["draws"]
        agent.fitness = record["fitness"]
        agent.games_since_last_reproduction = record["games_since_last_reproduction"]
        population.alive.append(agent)

    state = repo.load_simulation_state()
    population.tick = state["current_tick"]
    RETURN population, state["rng_state"]   # rng_state handled by the caller, see below
```

*(Pseudocode — an outline, not implementation.)*

## Seed / RNG continuity

- **Fresh start**: `rng = np.random.default_rng(seed)` where `seed` is `--seed` if given, else `config.random_seed`. The chosen seed is written into `simulation_config_history`'s first row (tick 0).
- **Resume, no `--seed` given (default)**: restore the *exact* persisted state — `rng = np.random.default_rng(); rng.bit_generator.state = json.loads(stored_state)` — continuing the identical stream, bit-for-bit, as if the run had never paused.
- **Resume, `--seed` given**: construct a brand-new `np.random.default_rng(seed)` instead of restoring the old state — a deliberate branch point. Append a new row to `simulation_config_history` recording the new seed value from this tick forward.
- `simulation_state`'s `rng_state` is upserted at the end of every tick (alongside the existing `repo.commit()` call), so a pause at any point captures exact continuation state — not just at deliberate checkpoints.

## Resume-time validation

Before `Population.load()` runs, compare the live `config.yaml`'s frozen fields (see classification above) against the `simulation_config` row already in the target database. Any mismatch — including a config field that exists in the live config but wasn't present when the snapshot was taken (schema drift on the config file itself) — refuses the resume outright with an error naming every mismatched field. This is a hard failure, not a warning: resuming with a mismatched `board_columns`, for instance, could otherwise silently corrupt agent reconstruction (existing weight vectors no longer matching the network shape a mismatched config implies).

## Dependencies

Builds on Phase 4b (`Agent.parent1_id`/`parent2_id`, needed by `Population.load()`) and everything before it. `numpy`'s `Generator.bit_generator.state` is stdlib-adjacent (already part of the `numpy` dependency); JSON serialization of it needs no new dependency.

## Definition of done

- Matches plan §11's literal Phase 5 DoD: a multi-hundred-tick run completes with no crashes, DB fills in as expected.
- A run started fresh, stopped partway (simulating an interruption), and resumed with no `--seed` override continues bit-for-bit identically to an uninterrupted run with the same starting seed.
- A resume with an explicit `--seed` override produces a valid but different continuation from that point forward.
- A resume attempt against a database with a deliberately mismatched frozen field (e.g. edited `board_columns` in `config.yaml` between runs) is refused with a clear, field-naming error — and the database is left untouched (no partial/corrupted state written).
- `simulation_config_history` correctly reflects a mid-run change to a mutable parameter (e.g. `tournament_size` edited in `config.yaml` between an initial run and a resume) as a new row at the resume tick, with the prior value's row left intact for earlier ticks.
- Full existing test suite continues to pass.

## Known limitations

- Mutable config changes only take effect at a resume boundary, not truly "live" mid-tick-loop — there's no mechanism (nor a need for one) to hot-reload `config.yaml` while ticks are actively running within a single invocation.
- No config-value versioning beyond the frozen/mutable split described above — sufficient for this project's scale and purpose, not a general-purpose migration system.
