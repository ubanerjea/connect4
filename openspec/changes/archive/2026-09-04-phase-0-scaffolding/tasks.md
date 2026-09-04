## 1. Environment & Tooling

- [x] 1.1 Install `uv` via `winget install astral-sh.uv` and verify `uv --version` succeeds
- [x] 1.2 Use `uv` to provision a Python interpreter (`uv python install`) and verify `uv run python --version` reports a real interpreter (not the WindowsApps stub)

## 2. Project Scaffolding

- [x] 2.1 Run `uv init --package` (or equivalent) at the repo root to generate `pyproject.toml` and the `src/evoconnect4/` layout, and verify `pyproject.toml` and `src/evoconnect4/__init__.py` exist
- [x] 2.2 Add `.gitignore` covering `.venv/`, `__pycache__/`, and `data/*.db`, and verify `git status` shows no `.venv` or cache noise after running commands
- [x] 2.3 Add `numpy` and `pyyaml` as runtime dependencies and `pytest` as a dev dependency via `uv add`, and verify `uv.lock` is generated and `pyproject.toml` lists all three

## 3. Subpackage Placeholders

- [x] 3.1 Create empty, importable placeholder subpackages `src/evoconnect4/{game,agent,evolution,storage,interface,analytics}/` each with an `__init__.py`, and verify `uv run python -c "import evoconnect4.game, evoconnect4.agent, evoconnect4.evolution, evoconnect4.storage, evoconnect4.interface, evoconnect4.analytics"` succeeds with no error

## 4. Config Module

- [x] 4.1 Create `config.yaml` at the repo root with all §10 tunable defaults from the project plan (population_size, board dimensions, hidden_layer_sizes, lifespan_range, mutation_rate_range, mutation_rate_tau, crossover_rate_range, crossover_rate_mutation_std, tournament_size, reproduction_interval_min/max, games_per_pair_per_tick, benchmark_every_n_ticks, benchmark_games_per_opponent, random_seed)
- [x] 4.2 Implement a typed `Config` dataclass and a loader function in `src/evoconnect4/config.py` (or `config/loader.py`) that reads `config.yaml` and returns a populated `Config` instance, and verify a round-trip test (load config, assert `config.population_size == 100`) passes
- [x] 4.3 Add `tests/test_config.py` covering the loader (valid file loads correctly; fields are typed) and verify `uv run pytest tests/test_config.py` passes

## 5. Entry Point

- [x] 5.1 Implement `run_simulation.py` (or `src/evoconnect4/run_simulation.py`) that loads config via the loader, imports every placeholder subpackage, prints the resolved config settings, and exits 0
- [x] 5.2 Verify `uv run python run_simulation.py` (or the equivalent module invocation) runs end-to-end with exit code 0 and printed output showing the resolved config values

## 6. End-to-End Verification

- [x] 6.1 Verify `uv run pytest` passes with zero failures across the (currently minimal) test suite
- [x] 6.2 Verify a clean checkout (`uv sync` then run the entry point) reproduces the same successful run, confirming `uv.lock` captures everything needed
