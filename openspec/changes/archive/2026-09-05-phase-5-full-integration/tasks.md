## 1. Storage: schema additions

- [x] 1.1 Add `simulation_config`, `simulation_config_history`, and `simulation_state` table definitions to `src/evoconnect4/storage/schema.py` (all `CREATE TABLE IF NOT EXISTS`, matching the existing style; `simulation_config` includes a `simulation_id TEXT NOT NULL` column) and verify `test_create_schema_creates_all_tables`-style assertions pass for the three new tables.
- [x] 1.2 Add `parent_avg_fitness REAL NOT NULL DEFAULT 0.0` to the `agents` table definition and verify a fresh schema creation includes it (`PRAGMA table_info(agents)`).

## 2. Storage: repository CRUD

- [x] 2.1 Extend `Repository.insert_agent` and `_row_to_agent` to accept/return `parent_avg_fitness`, and verify a round-trip test (insert with a non-zero value, read back, matches) passes.
- [x] 2.2 Add `Repository.insert_simulation_config(**fields)` and `Repository.get_simulation_config()` (frozen fields: `simulation_id`, `board_columns`, `board_rows`, `hidden_layer_sizes`, `weight_init_std`) and verify a round-trip test passes.
- [x] 2.3 Add `Repository.insert_simulation_config_history_row(tick, **fields)` (append-only; all mutable fields listed in design.md/proposal.md) and `Repository.get_effective_config_at_tick(tick)` (most recent row at or before `tick`), and verify: an initial tick-0 row is retrievable, and a later row at a higher tick does not affect a query for an earlier tick.
- [x] 2.4 Add `Repository.upsert_simulation_state(current_tick, rng_state)` and `Repository.get_simulation_state()` (single row, always overwritten), and verify repeated upserts leave only the latest values readable.

## 3. Population: persist parent_avg_fitness and add `load()`

- [x] 3.1 Update `Population._add_agent` to pass `parent_avg_fitness` through to `repo.insert_agent`, and verify an existing Phase 4b cull test (or a new one) confirms the value now round-trips through storage.
- [x] 3.2 Implement `Population.load(config, repo)` as a module-level or classmethod counterpart to `initialize()`: reconstruct every alive agent via `Genome.decode()` + `Agent(...)` (including `parent1_id`, `parent2_id`, `parent_avg_fitness`, and all live-stat fields from the stored record), restore `population.tick` from `simulation_state`, and return the population plus the persisted `rng_state` string for the caller to apply. Verify with a test that creates a population, runs several ticks, persists, reloads via `load()`, and asserts every alive agent's genome/lineage/stats match.
- [x] 3.3 Verify a reloaded population's tier-2 cull ordering test: with `cull_allow_immature_offspring=True`, an agent reconstructed via `load()` is ranked by its persisted `parent_avg_fitness`, not `0.0`.

## 4. Run lifecycle: CLI entry point

- [x] 4.1 Add `argparse`-based `--ticks` (default 500), `--seed` (no default; `None` means "not given"), and `--db` (default an auto-generated `data/evoconnect4_<YYYYMMDD_HHMMSS>.db` path) arguments to `run_simulation.py`, and verify `--help` lists all three with their described defaults.
- [x] 4.2 Implement the fresh-vs-resume decision: open a `Repository` at the target `--db` path, check `repo.list_agents(status="alive")`; empty → fresh path, non-empty → resume path. If alive agents exist but `repo.get_simulation_config()` returns nothing, raise a clear error (corrupt/foreign database) rather than silently choosing either path. Verify with tests covering all three cases (fresh, resume, corrupt).
- [x] 4.3 Implement the fresh-start path: seed = `--seed` if given else `config.random_seed`; generate a new `simulation_id` (`uuid.uuid4()`); call `Population.initialize()`; write the frozen `simulation_config` row (including `simulation_id`); write the tick-0 `simulation_config_history` row (including the resolved seed); run `--ticks` ticks; upsert `simulation_state` after every tick. Verify a multi-tick fresh run completes, leaves all three new tables populated, and that `simulation_config.simulation_id` is a non-empty, unique-looking string.
- [x] 4.4 Implement the resume path: load `simulation_config`, compare every frozen field against the live `Config` (per the allowlist in design.md/proposal.md); on any mismatch, refuse to resume with an error naming every mismatched field and make no writes; on match, call `Population.load()`, restore RNG (`--seed` given → new `default_rng(seed)` and append a new `simulation_config_history` row from this tick; not given → restore the exact persisted `bit_generator.state`), diff the live mutable config against the most recent history row and append a new history row only if something changed, then run `--ticks` further ticks. Verify with tests covering: identical-seed resume continues bit-for-bit identically to an uninterrupted run, `--seed`-override resume produces a valid but different continuation, a mismatched frozen field refuses the resume and leaves the database untouched, and a changed mutable field produces a new history row at the resume tick while the prior row is left intact.
- [x] 4.5 Wire `main()` to call the fresh or resume path based on the decision in 4.2, replacing the Phase 0 stub body.

## 5. Full-run verification

- [x] 5.1 Add or extend an integration test that runs `run_simulation.py`'s entry point (or its underlying function, called directly) for several hundred ticks against a temp `--db` path and asserts it completes without error, matching plan §11's literal Phase 5 DoD.
- [x] 5.2 Run the full existing test suite (`pytest`) and verify it still passes unchanged, confirming no regression to Phases 0-4b.
