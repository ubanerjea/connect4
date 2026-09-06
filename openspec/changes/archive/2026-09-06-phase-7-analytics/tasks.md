## 1. Dependencies

- [x] 1.1 Add `matplotlib` and `pandas` to `pyproject.toml`'s dependencies (update `uv.lock` accordingly), and verify `import matplotlib` / `import pandas` succeed in the project's virtual environment.

## 2. Single-run analytics: chart data extraction

- [x] 2.1 In new `src/evoconnect4/analytics/plots.py`, implement data-extraction functions reading via `Repository`: `fitness_over_time(repo)` (tick, avg/max/min fitness from `population_snapshots`), `population_size_over_time(repo)` (tick, population_size), `gene_drift_over_time(repo)` (tick, avg_lifespan, avg_mutation_rate), and `benchmark_win_rate_over_time(repo)` (tick, opponent_type, win_rate, via `list_benchmark_results()`). Verify each against a `Repository` fixture with known inserted snapshot/benchmark rows, asserting the returned data matches exactly what was inserted.

## 3. Single-run analytics: rendering + CLI

- [x] 3.1 Implement rendering functions (`plot_fitness_over_time`, `plot_population_size_over_time`, `plot_gene_drift_over_time`, `plot_benchmark_win_rate_over_time`) using `matplotlib`, each writing a PNG to a given output path; the fitness and benchmark-win-rate renderers additionally overlay a `pandas.Series.rolling(window).mean()` trend line on the raw series. Verify with a smoke test per chart: renders without error, and the output file exists with nonzero size.
- [x] 3.2 Implement the `plots.py` CLI entry point (`argparse`: `--db`, `--out-dir`) that opens a `Repository` against `--db`, creates `--out-dir` if it doesn't exist, and calls all four extraction+render pairs, writing four PNGs into it. Verify with an integration test that runs it against a small populated run database and asserts all four expected files exist with nonzero size.

## 4. Cross-simulation catalog: `analytics.db` schema

- [x] 4.1 In new `src/evoconnect4/analytics/catalog.py`, implement schema creation for `analytics.db`: `simulations` (`simulation_id` PK, `source_db_path`, `cataloged_at`, `last_cataloged_tick`, the frozen config fields, and the initial mutable config fields — same field set as `simulation_config`/`simulation_config_history`'s tick-0 row), `simulation_population_snapshots` (own autoincrement PK, `simulation_id`, tick, the `population_snapshots` fields, `source_best_agent_id`, `UNIQUE(simulation_id, tick)`), `simulation_benchmark_results` (own autoincrement PK, `simulation_id`, tick, `opponent_type`, `games_played`, `win_rate`, `source_agent_id`, `UNIQUE(simulation_id, tick, opponent_type)`). Verify a fresh `analytics.db` creation produces all three tables, and that the unique constraints reject a duplicate `(simulation_id, tick, ...)` insert.

## 5. Cross-simulation catalog: ETL + idempotency

- [x] 5.1 Implement the per-file cataloging step: given one run database path, read its `simulation_config` (skip, returning without error, if absent — not a run database, or predates the `simulation_id` addition), its `simulation_config_history` tick-0 row, and its `simulation_state.current_tick`; compare that current tick against the existing `simulations.last_cataloged_tick` for that `simulation_id` and skip if already caught up; otherwise upsert the `simulations` row and upsert every `population_snapshots`/`benchmark_results` row (keyed by their `UNIQUE` constraints) into the two rollup tables. Verify: cataloging a fresh run database produces the expected rows in all three catalog tables; cataloging a database with no `simulation_config` is skipped without raising.
- [x] 5.2 Implement the directory-scanning CLI entry point (`argparse`: `--runs-dir`, `--analytics-db`) that globs `*.db` files under `--runs-dir` (excluding `--analytics-db` itself) and runs the per-file step against each. Verify against a directory containing two or more run databases: `analytics.db`'s `simulations` table has exactly one row per run, and both rollup tables are populated.
- [x] 5.3 Verify idempotency with tests: running the catalog twice against an unchanged set of run databases leaves `analytics.db` unchanged the second time (no new or duplicate rows, `last_cataloged_tick` unchanged); advancing one run further (more ticks, via a Phase 5 resume) and re-cataloging adds only the newly-recorded snapshot/benchmark rows and updates `last_cataloged_tick`, without duplicating or altering previously-cataloged rows.

## 6. Full-suite verification

- [x] 6.1 Run the full existing test suite (`pytest`) and verify it still passes unchanged, confirming no regression to Phases 0-6.
