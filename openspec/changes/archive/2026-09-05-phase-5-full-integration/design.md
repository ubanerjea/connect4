## Context

Everything needed to run a real simulation already exists and is archived: game engine (Phase 1), agents/genome (Phase 2), storage (Phase 3), and a working tick loop with parametrized culling (Phase 4/4b). `run_simulation.py` is still the Phase 0 stub. `Repository.__init__` always calls `create_schema()` (all `CREATE TABLE IF NOT EXISTS`), so opening a `Repository` against any path — new or existing — is always safe; the fresh-vs-resume decision has to be made by inspecting content (alive agents), not file existence alone. `Agent` (Phase 4b) already carries `parent1_id`, `parent2_id`, and `parent_avg_fitness` in memory; `Population._add_agent` computes `parent_avg_fitness` at birth but never passes it to `repo.insert_agent`, so it is lost on any DB read today — grounding for this proposal's schema addition. No `data/*.db` files exist yet in this repo, so the `agents` table schema change has no real data to migrate.

See proposal.md for motivation; see the three delta specs for full behavioral requirements.

## Goals / Non-Goals

**Goals:**
- A CLI entry point that runs N ticks against a target database, deciding fresh-vs-resume from that database's content.
- Exact, bit-for-bit RNG continuation across a pause/resume by default, with an explicit opt-in to branch to a new seed.
- A frozen/mutable config-snapshot split that makes every run's database self-describing and query-able independent of the `config.yaml` that produced it.
- Closing the `parent_avg_fitness` persistence gap so `Population.load()` is a faithful reconstruction, not a lossy one.

**Non-Goals:**
- Any change to tick-loop evolutionary mechanics (Phase 4b's culling algorithm, reproduction timing, etc.) — this phase only adds persistence and an entry point around it.
- Config-value versioning or migration beyond the frozen/mutable split — an unclassified new config field defaults to frozen, full stop.
- Multi-machine or concurrent-writer database access — still a single SQLite file, single process.
- Benchmark-tick scheduling (Phase 6) and the CLI human-play interface (Phase 8).
- A general schema-migration mechanism for the new `agents.parent_avg_fitness` column — see Risks/Trade-offs.
- Building or wiring the cross-simulation analytics catalog itself — that's Phase 7; this phase only mints the `simulation_id` key it will need.

## Decisions

### Fresh-vs-resume detection: open the repo, then check for alive agents
Because `Repository.__init__` unconditionally creates any missing tables, "does the file exist" is not sufficient to distinguish fresh from resume (a stale empty file with only auto-created empty tables must still count as fresh). The entry point opens a `Repository` against `--db`, then calls `repo.list_agents(status="alive")`. Empty → fresh start. Non-empty → resume. If alive agents exist but `simulation_config` has no row, that is a corrupt or foreign database (not a resumable state and not "fresh" either, since it already has content) — this is a hard error, not a silent fallback to fresh.

### CLI argument parsing: stdlib `argparse`
No new dependency needed; consistent with the project's existing "stdlib where possible" stance (plain `sqlite3`, plain `input()`/`print()` for the human CLI). Alternatives (`click`, `typer`) would add a dependency for three flags with no subcommands — not justified here.

### `parent_avg_fitness` becomes a persisted, immutable-after-birth column
Rather than recomputing it at resume time by walking `parent1_id`/`parent2_id` back to their (possibly dead) parent records, `parent_avg_fitness` is computed once at birth (already true today, in memory) and now also persisted as a plain column on `agents`, alongside the other birth-time fields. This is simpler and cheaper than a lookup-based reconstruction, matches how every other birth-time field (`generation`, `lifespan`, `mutation_rate`, `crossover_rate`) is already handled, and needs no new join or query pattern. This does mean the original `plans/phase-5-full-integration.md` brief's pseudocode (which assumed a live `repo.get_agent()` lookup at cull time via `parent1_id`/`parent2_id`) is superseded by this simpler approach, made possible because Phase 4b's actual implementation already computes and carries `parent_avg_fitness` on `Agent` — the brief predates that implementation detail.

### Config classification: allowlist (fail-safe), not a denylist
Any config field not explicitly listed as mutable is frozen by default. This was a direct, explicit correction from earlier design discussion: `hidden_layer_sizes`/`weight_init_std` are only ever consulted once today (at generation-0 `random_genome()` calls), so a denylist approach might have left them unclassified-and-therefore-mutable by omission. An allowlist makes "safe to change mid-lifetime" an opt-in property instead of a default, which matters because `hidden_layer_sizes` specifically must stay consistent across the whole population for `crossover()`'s per-weight mask to remain shape-compatible between any two agents, and `board_columns`/`board_rows` are baked into every existing agent's stored flat weight vector length.

### Two config tables, not one: frozen vs. mutable-with-history
`simulation_config` (single row, written once) and `simulation_config_history` (append-only, one row per point the effective mutable config changed) are kept separate rather than combined into one config table with nullable "changed at" columns, because they have genuinely different write patterns (write-once vs. append-only) and different query shapes ("what was true, period" vs. "what was true as of tick N"). `simulation_state` (current tick + RNG bytes) is a third, different-again table because it is not a configuration record at all — it is mechanical execution state, overwritten every tick, never queried for its history.

### `simulation_config` carries a `simulation_id`, minted once at fresh-population creation, never validated
A UUID4 string (stdlib `uuid.uuid4()`, no new dependency), generated only on a fresh start and never regenerated on resume — a resume reads it from the existing row and carries it forward unchanged. It exists purely as a stable, rename-proof key for Phase 7's planned cross-simulation analytics catalog (`plans/phase-7-analytics.md`) to tag its rollup rows and check idempotency against; this phase has no internal use for it beyond storing and returning it unchanged. Because it isn't derived from `config.yaml`, it is not part of the resume-time frozen-field match/mismatch check described below (there is no live-config counterpart to compare it against) — it is simply read back on resume, not validated. Minting it here, while `simulation_config`'s schema is still being greenfielded, avoids retrofitting an identifier onto already-existing run databases later — the same migration-avoidance reasoning as the `parent_avg_fitness` addition above, pre-empted before it becomes a real gap.

### RNG state stored separately from `random_seed`
`random_seed` (a human-meaningful, tick-stamped fact worth querying — "what seed produced this run?") lives in `simulation_config_history`. The opaque `Generator.bit_generator.state` continuation blob lives in `simulation_state` instead, upserted at the end of every tick alongside the existing `repo.commit()` call. This keeps the history table queryable and human-readable while keeping the frequently-rewritten opaque blob out of an append-only table (which would otherwise grow one row per tick).

## Risks / Trade-offs

- **No migration path for the new `agents.parent_avg_fitness` column** → Acceptable at this project's stage: no `data/*.db` file exists yet in the repository, and `CREATE TABLE IF NOT EXISTS` would not retrofit the column onto a pre-existing table anyway. If a real run's database predates this change, it would need to be recreated. Documented here rather than solved with a migration system, per the Non-Goals above.
- **Hard refusal on frozen-config mismatch could block a resume the user actually wants** (e.g., they genuinely want to change `board_columns` mid-project) → Deliberate: silently allowing it would make existing agents' stored weight vectors unreconstructable against a changed network shape. The correct path in that case is a fresh run at a new `--db` path, not a resume.
- **`simulation_config_history` could grow unboundedly over a very long-lived population with frequently-edited config** → Out of scope at this project's scale (per plan §6's own note: "thousands of rows per run, not millions"); a row is appended only on an actual detected change at a resume boundary, not per tick.

## Open Questions

None — every decision above was resolved during the design conversation that produced `plans/phase-5-full-integration.md`, and the one implementation-level gap found while grounding this proposal in the current code (`parent_avg_fitness` persistence) is resolved above rather than deferred.
