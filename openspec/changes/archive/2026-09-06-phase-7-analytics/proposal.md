## Why

Every simulation run lives in its own isolated SQLite file (Phase 5's "one database file = one population's continuous lifetime" principle), and nothing yet turns that stored history into anything visual or comparable. `analytics/` and `interface/` are still empty stub packages from Phase 0 scaffolding. This phase closes the loop: charts from a single run's database, and a way to compare multiple runs without hand-writing `ATTACH` SQL every time.

## What Changes

- Add a plotting CLI (`analytics/plots.py`, `python -m evoconnect4.analytics.plots --db <path> --out-dir <dir>`) generating four PNG charts from a single run's database: population fitness over time, benchmark win-rate over time, population size over time, and gene drift — each with a `pandas`-computed rolling-average trend line overlaid on the raw series. Lineage walk (plan §9's fifth, "nice-to-have" chart) is explicitly deferred.
- Add a catalog ETL step (`analytics/catalog.py`, `python -m evoconnect4.analytics.catalog --runs-dir <dir> --analytics-db <path>`) that scans a directory of run databases and rolls up aggregate-only data (never `agents`/`games`) into a shared `data/analytics.db`, keyed by `simulation_id`, idempotent across re-runs.
- Add three new tables to `analytics.db`: `simulations` (one row per cataloged run — frozen config + initial mutable config + bookkeeping), `simulation_population_snapshots`, `simulation_benchmark_results` (both tagged rollups of the source tables).
- Add `matplotlib` and `pandas` as project dependencies.

## Capabilities

### New Capabilities
- `single-run-analytics`: chart generation (data extraction + rendering) from a single run's database.
- `cross-simulation-catalog`: the `analytics.db` schema and the idempotent ETL step that populates it from many run databases.

### Modified Capabilities
- `database-storage`: adds the ability to list all population snapshots (not just the latest), discovered necessary while implementing `single-run-analytics`. `population-evolution` and `run-lifecycle` are unaffected. The catalog step reads existing run databases read-only and never changes their schema.

## Impact

- `src/evoconnect4/analytics/plots.py` — new: chart data-extraction functions + `matplotlib`/`pandas` rendering functions + CLI entry point.
- `src/evoconnect4/analytics/catalog.py` — new: `analytics.db` schema creation, the scan-and-upsert ETL loop, CLI entry point.
- `pyproject.toml` — add `matplotlib` and `pandas` dependencies.
- `src/evoconnect4/storage/repository.py` — add `Repository.list_snapshots(*, tick: int | None = None)`, mirroring `list_games`/`list_agents`/`list_benchmark_results`'s existing convention. Discovered necessary during implementation: `Repository` only exposed `get_latest_snapshot()`, which can't serve a "population fitness/size/gene-drift over time" chart that needs every tick's snapshot, not just the most recent one.
- No changes to `schema.py`, `evolution/population.py`, or `run_simulation.py` — this phase only reads existing run databases, through the existing (now slightly extended) `Repository` class for single-run plotting and through direct read-only SQLite access for the catalog.
