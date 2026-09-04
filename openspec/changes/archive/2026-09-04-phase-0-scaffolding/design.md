## Context

No Python tooling exists on this machine yet — `python`/`python3` resolve only to the Windows Store alias stub, not a real interpreter. The project plan (`plans/evoconnect4_project_plan.md` §7) sketched a flat `requirements.txt`-style layout, written before any tooling decision was made. This design fills in the concrete choices needed to scaffold a runnable project, reached through discovery with the user (see proposal.md - Why).

## Goals / Non-Goals

**Goals:**
- A `uv`-managed project that installs cleanly and gives a real, working Python environment.
- A package layout and config approach that later phases (1-8 of the plan's roadmap) can build directly into, without restructuring.
- An entry point that proves the skeleton wires together, with zero real game/agent/evolution logic.

**Non-Goals:**
- Any real implementation inside `game/`, `agent/`, `evolution/`, `storage/`, `interface/`, `analytics/` — those are later phases.
- Choosing or pinning exact dependency versions beyond what's needed to run (`uv` resolves and locks these).
- CI/CD, packaging for distribution, or Docker — out of scope for a local toy project's Phase 0.

## Decisions

**`uv` over `venv`+`requirements.txt` or `conda`.** The plan's §7 didn't mandate a specific tool, and this machine has no existing Python investment to preserve. `uv` was chosen for speed and because it can fetch a real interpreter itself, solving the "no Python installed" blocker in one step. Trade-off: one more tool to have installed (via `winget`) versus using only what's already on the system.

**`src/evoconnect4/` layout over the plan's flat nesting.** `uv init --package` scaffolds `src/`-layout natively; fighting that convention would add friction for no benefit. The module boundaries from plan §7 (`game/`, `agent/`, `evolution/`, `storage/`, `interface/`, `analytics/`) are preserved exactly — only the root nesting and the `pyproject.toml`/`requirements.txt` choice changed.

**All subpackages scaffolded now, as empty placeholders, rather than created lazily per-phase.** Considered creating each subpackage only when its own roadmap phase starts (leaner Phase 0, no empty dirs). Chose scaffolding all of them now so `run_simulation.py`'s "confirm all subpackages import cleanly" check (see proposal.md - What Changes) has something real to import against from Phase 0 onward, and so the full package structure is visible in one place from the start.

**`config.yaml` + typed-dataclass loader over a pure-Python dataclass or a loader returning a plain dict.** A pure dataclass (defaults hardcoded in Python) was simplest but keeps tunables from plan §10 mixed into code. A loader returning a plain dict was rejected because call sites lose autocomplete/type-checking (`config["population_size"]` vs `config.population_size`) with no offsetting benefit. YAML-as-source + a loader that parses into a typed dataclass gets both: tunables live in a human-editable file, and consuming code still gets typed, checked access. Adds one dependency (`pyyaml`).

**Stub entry point does config-load-and-print only, not a simulated tick loop.** A version that also prints a fake "tick 0..N" loop was considered, to rehearse the shape of the real loop in plan §4.2 early. Rejected for Phase 0: the roadmap's own Definition of Done for this phase is "entry point runs end-to-end with stub logic" (plan §11) — the real tick loop's shape and behavior belong to Phase 4 (Evolution core), where it can be built against real agents and games rather than hand-waved.

## Risks / Trade-offs

- [`uv` requires an install step (via `winget`) before anything else works] → Documented as the first task; low risk since `winget` is already present on this machine.
- [Scaffolding all subpackages now creates several empty `__init__.py` files that sit unused until their phase] → Accepted trade-off per the decision above; cost is a few trivial files, not complexity.
- [YAML adds a runtime dependency (`pyyaml`) that a pure-dataclass config wouldn't need] → Accepted; the human-editability benefit was the deciding factor and the dependency is lightweight and well-maintained.
