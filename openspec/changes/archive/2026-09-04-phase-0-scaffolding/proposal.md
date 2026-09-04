## Why

EvoConnect4 currently exists only as a project plan (`plans/evoconnect4_project_plan.md`) — no repo structure, dependency management, or entry point exists yet. Phase 0 of the plan's roadmap (§11) calls for a thin scaffold — layout, config, dependencies, and a stub entry point — proven end-to-end before any real game/agent/evolution logic is built in later phases.

## What Changes

- Add `uv`-managed Python project: `pyproject.toml` + `uv.lock`, targeting a `src/evoconnect4/` package layout.
- Add empty, importable placeholder subpackages matching the plan's §7 structure: `game/`, `agent/`, `evolution/`, `storage/`, `interface/`, `analytics/`.
- Add `config.yaml` holding the §10 tunable defaults, plus a loader that parses it into a typed dataclass.
- Add `run_simulation.py` as the entry point: loads config via the loader, prints the resolved settings, confirms all subpackages import cleanly, and exits 0.
- Add `pytest` as a dev dependency and an empty `tests/` directory.
- Add `.gitignore` covering `.venv/`, `__pycache__/`, and `data/*.db`.
- Declare `numpy` and `pyyaml` as runtime dependencies (used by later phases' network code and this phase's config loader respectively); defer `matplotlib` until Phase 7 (analytics) actually needs it.

No game rules, neural network, evolution loop, or database logic is implemented in this change — those are Phases 1-6 of the plan's roadmap and are explicitly out of scope here.

## Capabilities

### New Capabilities

None. This is project scaffolding — no observable system behavior exists yet for a spec to describe.

### Modified Capabilities

None.

## Impact

- New files: `pyproject.toml`, `uv.lock`, `.gitignore`, `src/evoconnect4/**`, `config.yaml`, `run_simulation.py`, `tests/` (empty).
- New dependencies: `uv` (tooling, not a Python package), `numpy`, `pyyaml` (runtime), `pytest` (dev).
- No existing code, specs, or database affected — this is the first code in the repo.
