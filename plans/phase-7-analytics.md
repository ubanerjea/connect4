# Phase 7 — Analytics: Single-Run Plots & Cross-Simulation Catalog

*Plotting scripts against one run's database (plan §9), plus a decoupled ETL step that rolls aggregate-only data from many run databases into a shared, queryable `analytics.db`. See `evoconnect4_project_plan.md` §11.*

This document is a self-contained brief for entering the OpenSpec propose/apply cycle. It assumes Phase 5 (`plans/phase-5-full-integration.md`) is already built and archived, in particular the `simulation_id` field on `simulation_config` (added specifically to give this phase a stable key — see Dependencies). Phase 6 (baseline benchmarking) is also assumed built, since the catalog rolls up `benchmark_results`. No open questions remain — every decision below was explicitly resolved in the design conversation that produced this document.

## Why

Every simulation run lives in its own SQLite file (Phase 5's "one database file = one population's continuous lifetime" principle) — deliberately, so runs never bleed into each other and each file stays a complete, self-contained, portable record. But that isolation has a cost once you have more than one or two run files: comparing them means manually `ATTACH`-ing files and hand-writing cross-file SQL every time, which doesn't scale past a handful of ad hoc comparisons. This phase adds two things: the original plan §9 single-run plotting scope, and a lightweight catalog mechanism that makes "compare N runs" a normal query against one file instead of a manual `ATTACH` exercise every time.

## Scope

**In scope:**
1. A plotting CLI (`analytics/plots.py`, `matplotlib` + `pandas`), invoked as `python -m evoconnect4.analytics.plots --db <path> --out-dir <dir>`, generating one PNG per chart into `--out-dir` against a single run's database — four of plan §9's five charts: population fitness over time, baseline benchmark win-rate over time, population size over time, and gene drift (avg lifespan / mutation rate). The fitness and win-rate charts overlay a `pandas`-computed rolling-average trend line on the raw (expectedly noisy, per plan §5) series. The fifth, lineage walk, is deferred — see Out of scope.
2. A catalog ETL step that scans a directory of run databases and rolls up **aggregate-only** data — never the heavy per-run tables — into a shared `data/analytics.db`, tagged by `simulation_id`.
3. Idempotent re-cataloging: running the catalog step again only inserts/refreshes runs that are new or have advanced further (more ticks) since they were last cataloged; it never duplicates rows.
4. A `simulations` master table in `analytics.db` — one row per cataloged run, combining that run's frozen config, its initial (tick-0) mutable config, and bookkeeping fields (source path, last-cataloged tick, catalog timestamp) — so a single `WHERE`/`GROUP BY` over `simulations` filters or buckets runs by any config value.

**Out of scope:**
- **Lineage walk** (plan §9's fifth chart, explicitly marked "nice-to-have" there): a family-tree render is a genuinely different kind of visualization from the other four (graph/DAG layout, not a time series — crossover gives every agent two parents, so it's a DAG, not a strict tree, and needs a depth/breadth cap to stay readable on a population of any real size). Deferred rather than built half-heartedly; a future extension.
- Pre-built cross-run comparison scripts against `analytics.db` (e.g., "average final win-rate grouped by `tournament_size`") — the catalog's own DoD is that `analytics.db` is shaped for this kind of `pandas` one-liner (flat `simulations` table, tidy rollup tables), not that Phase 7 ships specific pre-baked comparison reports for questions nobody's asked yet.
- Copying `agents` or `games` into the shared database — these stay in each run's own file, reachable via `ATTACH` for the rare case a cross-run comparison needs per-agent or per-game detail (e.g. "show me the actual best agent's lineage from run X"). The catalog is for trend/aggregate comparison across runs, not a full data warehouse.
- Rolling up the full `simulation_config_history` (every mid-run config change) into the catalog — only the tick-0 initial config is captured per run. A user who needs a specific run's full config-change history can `ATTACH` that one file directly; that's already a cheap, well-supported operation and duplicating it into the shared DB buys little for a project at this scale.
- Automatically running the catalog step as part of every `run_simulation.py` invocation — it is a separate, explicit step (its own script/CLI command), decoupled from a run's own write path and safe to skip, re-run, or run against a whole directory of old runs at once.
- A general-purpose data warehouse, schema migration system, or query UI — `analytics.db` is a plain SQLite file, queried the same stdlib way as any run file.
- Multi-machine or concurrent-writer access to `analytics.db` — same single-file, single-process assumption as everywhere else in this project.

## Core principle: aggregate-only, decoupled, idempotent

Three deliberate constraints shape this design, each chosen to avoid a specific failure mode discussed while designing this phase:

```
+------------------------------------------------------------------+
| Why NOT copy everything into analytics.db on every run?           |
+------------------------------------------------------------------+
| agents / games are per-run detail tables (thousands of rows,      |
| full move histories) -- copying them duplicates the bulk of each  |
| run's storage for no benefit most comparisons need. Only the      |
| already-aggregated tables (population_snapshots, benchmark_       |
| results) plus one config-summary row per run go into the catalog. |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| Why NOT run the catalog automatically at the end of every run?    |
+------------------------------------------------------------------+
| Phase 5 deliberately keeps each run's file isolated and its write |
| path self-contained (no shared file every run must successfully  |
| write to). Coupling catalog ETL to run completion would reattach  |
| that dependency -- a crash or interruption in the shared          |
| analytics.db write shouldn't be able to affect a run's own        |
| success. The catalog is a separate, explicit, re-runnable step.   |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| Why does re-running the catalog need to be safe?                  |
+------------------------------------------------------------------+
| A run can be paused and resumed (Phase 5), so "cataloging" isn't  |
| necessarily a one-time, run-is-done event -- someone may want to  |
| catalog an in-progress run, then catalog it again later once it's |
| advanced further. Idempotency based on simulation_id + last-      |
| cataloged tick makes this safe to do at any time, any number of   |
| times, without duplicate rows.                                    |
+------------------------------------------------------------------+
```

## Design: `plots.py`

Each of the four charts is built from two functions, not one, so the chart's underlying data is independently testable without asserting on rendered pixels:

```
def fitness_over_time(repo) -> list[tuple[int, float, float, float]]:
    -- (tick, avg_fitness, max_fitness, min_fitness), one row per
    -- population_snapshots row -- plain data, ordinary unit-testable
    -- assertions (e.g. "tick 10's row has the values inserted at tick 10")

def plot_fitness_over_time(data, out_path) -> None:
    -- pandas.Series(...).rolling(window).mean() over avg_fitness for the
    -- smoothed trend line, overlaid on the raw series; matplotlib renders
    -- both to out_path. Covered only by a smoke test: runs without error,
    -- produces a nonzero-size PNG file.
```

The same split applies to the other three charts (`population_size_over_time`, `benchmark_win_rate_over_time` -- one rolling-smoothed line per `opponent_type`, `gene_drift_over_time` -- avg lifespan and avg mutation rate as two lines). `plots.py`'s CLI entry point (`python -m evoconnect4.analytics.plots --db <path> --out-dir <dir>`) calls all four extraction+render pairs against the given run's `Repository` and writes one PNG per chart into `--out-dir` (created if missing).

## New storage: `data/analytics.db`

```
+---------------------------------------------------------------------+
|  simulations  (one row per cataloged run -- the run's "identity")    |
+---------------------------------------------------------------------+
|  simulation_id (PK, matches the source run's simulation_config.     |
|    simulation_id), source_db_path, cataloged_at, last_cataloged_tick |
|                                                                       |
|  -- copied from the source run's simulation_config (frozen):        |
|  board_columns, board_rows, hidden_layer_sizes, weight_init_std      |
|                                                                       |
|  -- copied from the source run's simulation_config_history tick-0    |
|  row (the run's *initial* mutable config -- not its full history):  |
|  population_size, lifespan_range, lifespan_mutation_scale,           |
|  mutation_rate_range, mutation_rate_tau, crossover_rate_range,       |
|  crossover_rate_mutation_std, tournament_size,                       |
|  reproduction_interval_min/_max, games_per_pair_per_tick,            |
|  benchmark_every_n_ticks, benchmark_games_per_opponent,               |
|  random_seed, cull_fraction_range, cull_fraction_beta_a,             |
|  cull_fraction_beta_b, cull_allow_immature_offspring                  |
+---------------------------------------------------------------------+

+---------------------------------------------------------------------+
|  simulation_population_snapshots  (rollup, tagged by simulation_id)  |
+---------------------------------------------------------------------+
|  own PK (fresh autoincrement -- source snapshot_ids collide across   |
|  files, so they aren't reused as this table's key), simulation_id,   |
|  tick, population_size, avg_fitness, max_fitness, min_fitness,       |
|  avg_lifespan, avg_mutation_rate, source_best_agent_id (informational|
|  only -- not a real FK, since agents never enter this database)      |
+---------------------------------------------------------------------+

+---------------------------------------------------------------------+
|  simulation_benchmark_results  (rollup, tagged by simulation_id)     |
+---------------------------------------------------------------------+
|  own PK (fresh autoincrement, same reasoning as above), simulation_id|
|  tick, opponent_type, games_played, win_rate, source_agent_id        |
|  (informational only, same reasoning as above)                       |
+---------------------------------------------------------------------+
```

`UNIQUE(simulation_id, tick, ...)`-style constraints on the two rollup tables (matching each source table's natural per-tick grain) let a re-catalog `INSERT OR REPLACE`/upsert cleanly instead of needing a separate "have I seen this row" check per row — the idempotency check that matters is at the run level (`simulations.last_cataloged_tick` vs. the source file's current tick), not the individual-row level.

## The catalog step

A standalone script (e.g. `analytics/catalog.py`, invoked as `python -m evoconnect4.analytics.catalog [--runs-dir data/] [--analytics-db data/analytics.db]`) that:

```
FOR each *.db file in runs_dir (excluding the analytics db itself):
    OPEN it read-only, read simulation_config (skip files with none --
      not a run database, or predates Phase 5's simulation_id addition)
    simulation_id := simulation_config.simulation_id
    source_current_tick := simulation_state.current_tick

    existing := SELECT last_cataloged_tick FROM analytics.simulations
                WHERE simulation_id = ?
    IF existing is not None AND existing >= source_current_tick:
        SKIP (already fully cataloged, nothing new to add)

    UPSERT analytics.simulations row (frozen config + tick-0 mutable
      config + source_db_path + cataloged_at=now + last_cataloged_tick
      = source_current_tick)
    UPSERT (INSERT OR REPLACE keyed by simulation_id+tick) every
      population_snapshots row into simulation_population_snapshots
    UPSERT every benchmark_results row into simulation_benchmark_results
```

*(Pseudocode — an outline of the algorithm, not implementation.)*

Read access to each source file uses SQLite's `ATTACH DATABASE` (or a plain second connection) — no change needed to any run file, and no lock contention with a run that might still be actively writing to it beyond SQLite's normal same-file concurrent-reader support. An optional `--catalog` flag on `run_simulation.py` can invoke this same function scoped to just the file that run just used, as a convenience — but the standalone, directory-scanning script is the primary interface, since it is also what lets someone catalog a batch of older runs at once.

## Definition of done

- Matches plan §11's Phase 7 DoD for plotting: the four in-scope charts (population fitness, benchmark win-rate, population size, gene drift) generate correctly from a single completed run's database.
- `python -m evoconnect4.analytics.plots --db <path> --out-dir <dir>` produces four nonzero-size PNG files in `--out-dir`.
- Each chart's data-extraction function is independently unit-tested against a `Repository` fixture, without invoking `matplotlib`.
- Running the catalog step against a directory containing two or more run databases produces a queryable `analytics.db` whose `simulations` table has one row per run, and whose rollup tables let a single query (e.g. average final benchmark win-rate grouped by `tournament_size`) compare across those runs without `ATTACH`.
- Running the catalog step twice against the same, unchanged set of run databases is a no-op the second time (no duplicate or changed rows).
- Cataloging a run, advancing it further (more ticks via a Phase 5 resume), then re-cataloging picks up only the newly-added snapshot/benchmark rows and updates `last_cataloged_tick` — it does not duplicate the rows already cataloged.
- A run database missing `simulation_config.simulation_id` (i.e., predating Phase 5's addition, or not a run database at all) is skipped rather than crashing the catalog step.
- Full existing test suite continues to pass.

## Dependencies

Builds on Phase 5's `simulation_config.simulation_id` (the stable key this phase's idempotency and joins are keyed on — without it, the catalog would have to fall back to file paths, which break under renames) and Phase 6's `benchmark_results` (the catalog rolls it up; before Phase 6 lands, that rollup table would simply stay empty). New external dependencies: `matplotlib` and `pandas` (plan §7 already anticipates both), added to `pyproject.toml` — `pandas` is a real dependency, not optional, used for the rolling-average smoothing in `plots.py` today and available for ad hoc cross-run analysis against `analytics.db` later (see the design conversation that produced this document for use cases considered). The catalog step itself needs only stdlib `sqlite3`.

## Known limitations

- The catalog is a point-in-time snapshot of each run's aggregate data as of whenever it was last run — it is not a live view. Re-run it to pick up runs that have advanced further.
- No cross-run identity beyond `simulation_id` — if two independent runs happen to be *configured* identically, they still get separate rows; the catalog doesn't attempt to group or deduplicate by configuration similarity, only by identity.
- `source_best_agent_id` / `source_agent_id` in the rollup tables are informational pointers back into the originating file (combine with that row's `simulation_id` → `simulations.source_db_path` to actually look one up) — they are not enforced foreign keys, since the referenced `agents` table doesn't exist in `analytics.db`.
