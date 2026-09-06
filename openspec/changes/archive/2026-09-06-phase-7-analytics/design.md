## Context

`analytics/` and `interface/` are still empty stub packages (just `__init__.py`) from Phase 0. Every run's database already contains everything these two capabilities need: `population_snapshots` (one row per tick — size, avg/max/min fitness, avg lifespan, avg mutation rate), `benchmark_results` (one row per opponent per benchmark tick — Phase 6), and the frozen/mutable config-snapshot tables from Phase 5 (`simulation_config` — including `simulation_id`, minted specifically for this phase's use — `simulation_config_history`, `simulation_state`). No `data/*.db` files exist yet in this repo (no real run has been executed outside tests), so nothing here has real data to migrate or validate against yet.

See proposal.md for motivation; see the two delta specs for full behavioral requirements.

## Goals / Non-Goals

**Goals:**
- Four charts (fitness, benchmark win-rate, population size, gene drift) generated from any single run's database via one CLI invocation.
- A shared `analytics.db` that lets a single SQL query compare aggregate trends across many independently-run databases, without hand-written `ATTACH` statements.
- Both pieces read-only against existing run databases — neither touches `schema.py` or any run's own file. (`Repository` itself gained one small additive read method — see Decisions — but nothing about its existing behavior changed.)

**Non-Goals:**
- Lineage walk (plan §9's fifth chart) — a graph/DAG render, not a time series; genuinely more implementation work (layout, depth/breadth capping) than the other four combined. Deferred as a future extension, consistent with plan §9's own "nice-to-have" framing.
- Pre-built cross-run comparison reports against `analytics.db` — the catalog's job is to make the data `pandas`-one-liner-shaped, not to guess which comparisons someone will eventually want.
- Copying `agents`/`games` into `analytics.db` — stays per-run-file-only, reachable via `ATTACH` for the rare case a cross-run question needs per-agent/per-game detail.
- Automatically invoking the catalog step from `run_simulation.py` — the catalog is a separate, explicit, re-runnable step, decoupled from every run's own write path (see Decisions).
- A general-purpose data warehouse, schema migration system, multi-machine access, or query UI for `analytics.db` — a plain SQLite file, queried the same stdlib way as any run file.

## Decisions

### `Repository` gained one additive read method: `list_snapshots`
Discovered necessary during implementation, not anticipated in the original proposal: `Repository` only exposed `get_latest_snapshot()`, which returns a single row and can't serve a chart that needs *every* tick's snapshot. `list_snapshots(*, tick: int | None = None)` mirrors the exact one-optional-filter convention `list_games`/`list_agents`/`list_benchmark_results` already use. No existing behavior changed; this is additive only.

### Data extraction is separated from rendering, in both capabilities
For `single-run-analytics`: each chart is built from a data-extraction function (returns plain tuples/lists, directly assertable against what was inserted into a `Repository` fixture) and a separate rendering function (`matplotlib`/`pandas`, covered only by a smoke test — runs without error, produces a nonzero-size PNG). Matplotlib output isn't meaningfully assertable in a unit test, so this split is what makes the actual data logic testable at all. The same split conceptually applies to the catalog's upsert logic (compute-what-changed vs. write-it), though the catalog's core testable unit is really "does the analytics.db end up in the right state," which is directly assertable via plain SQL reads.

### `pandas` is a real dependency, used now for rolling-average smoothing
Plan §5 explicitly expects population fitness to be "noisy, possibly non-monotonic" — a raw line chart of that is hard to read. `pandas.Series(...).rolling(window).mean()` overlaid on the raw series (population-fitness and benchmark-win-rate charts) is a small, direct improvement to two already-in-scope charts. `pandas` is not brought in as a maybe-later convenience; it does real work in this phase. It also happens to be the natural tool for ad hoc cross-run analysis against `analytics.db` later (`pd.read_sql_query` + `.groupby()`/`.corr()`/`merge_asof`), but that usage is explicitly not built into any shipped script this phase — see Non-Goals.

### Catalog step is a separate, explicit, directory-scanning script — never auto-invoked
Phase 5 deliberately keeps every run's file isolated and its write path self-contained (no shared file a run's own success depends on). Coupling catalog ETL to run completion would reattach exactly that dependency — a crash or interruption in a shared `analytics.db` write shouldn't be able to affect a run's own success. So `analytics/catalog.py` is invoked independently (`--runs-dir`/`--analytics-db`), and it's a directory scanner rather than a single-file tool specifically so it can also catalog a batch of older runs at once, not just "the run that just finished."

### Idempotency is keyed at the run level, not the row level
`simulations.last_cataloged_tick` (compared against the source database's current tick from `simulation_state`) decides whether a run needs (re-)cataloging at all; `UNIQUE(simulation_id, tick, ...)`-style constraints on the two rollup tables let a needed re-catalog `INSERT OR REPLACE` cleanly instead of a per-row "have I seen this" check. This has to be safe to run any number of times, at any point in a run's lifecycle, because Phase 5 runs can be paused and resumed — "cataloging" isn't a one-time, run-is-done event.

### `analytics.db`'s schema is a new, separate concern from `database-storage`
`simulations`/`simulation_population_snapshots`/`simulation_benchmark_results` live in their own database file, managed by their own connection/module (`catalog.py`), not through the `Repository` class or `schema.py`. This is why `cross-simulation-catalog` is its own capability rather than a delta on `database-storage` — the two are genuinely different storage layers with different lifecycles, not one schema growing new tables.

### Rollup tables get their own fresh primary keys, not the source tables' ids
Source `snapshot_id`/`benchmark_id` values collide across independent run files (each starts its own autoincrement sequence at 1), so the rollup tables can't reuse them as their own primary key — they get a fresh autoincrement key, with `(simulation_id, tick, ...)` as the natural per-row identity for the idempotent upsert.

## Risks / Trade-offs

- **`source_best_agent_id`/`source_agent_id` in the rollup tables aren't real foreign keys** (the referenced `agents` table doesn't exist in `analytics.db`) → accepted; they're informational pointers back into the originating file, combined with that row's `simulation_id` → `simulations.source_db_path` to actually look one up if needed.
- **No cross-run identity beyond `simulation_id`** — two independently-run, identically-configured runs still get separate `simulations` rows; the catalog doesn't attempt to deduplicate by configuration similarity. Accepted — identity by `simulation_id` is unambiguous; similarity-based grouping is a different, harder problem not needed for this phase's goals.
- **The catalog is a point-in-time snapshot**, not a live view — re-run it to pick up runs that have advanced further. Accepted, consistent with it being an explicit, decoupled step rather than automatic.
- **`matplotlib`/`pandas` are new dependencies** with real install/wheel weight → accepted; both were already anticipated in plan §7's own architecture table, and there's no lighter-weight stdlib alternative for chart rendering.

## Open Questions

None — every decision above was resolved during the design conversation that produced `plans/phase-7-analytics.md`, including this session's additions (CLI shape for `plots.py`, the data/render split, the `pandas` justification, and deferring lineage walk).
