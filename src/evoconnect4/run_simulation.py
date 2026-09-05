"""CLI entry point for a headless evolutionary run (plan Sec7/Sec11 Phase 5).

Fresh-vs-resume run lifecycle, RNG-state persistence, and frozen/mutable
config snapshotting -- see plans/phase-5-full-integration.md for the design.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np

from evoconnect4.config import Config, load_config
from evoconnect4.evolution.population import Population
from evoconnect4.storage.repository import Repository

FROZEN_FIELDS = ("board_columns", "board_rows", "hidden_layer_sizes", "weight_init_std")

MUTABLE_FIELDS = (
    "population_size",
    "lifespan_range",
    "lifespan_mutation_scale",
    "mutation_rate_range",
    "mutation_rate_tau",
    "crossover_rate_range",
    "crossover_rate_mutation_std",
    "tournament_size",
    "reproduction_interval_min",
    "reproduction_interval_max",
    "games_per_pair_per_tick",
    "benchmark_every_n_ticks",
    "benchmark_games_per_opponent",
    "random_seed",
    "cull_fraction_range",
    "cull_fraction_beta_a",
    "cull_fraction_beta_b",
    "cull_allow_immature_offspring",
)
_MUTABLE_FIELDS_EXCLUDING_SEED = tuple(f for f in MUTABLE_FIELDS if f != "random_seed")


class SimulationLifecycleError(Exception):
    """Base for errors that should abort the run without corrupting the database."""


class FrozenConfigMismatch(SimulationLifecycleError):
    def __init__(self, mismatches: dict[str, tuple]) -> None:
        self.mismatches = mismatches
        details = ", ".join(f"{field}: recorded={recorded!r} live={live!r}" for field, (recorded, live) in mismatches.items())
        super().__init__(f"Cannot resume: frozen configuration mismatch ({details})")


class CorruptDatabaseError(SimulationLifecycleError):
    pass


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a headless EvoConnect4 evolutionary simulation.")
    parser.add_argument("--ticks", type=int, default=500, help="Number of ticks to run this invocation (default: 500)")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed override (fresh: falls back to config.yaml's random_seed; "
        "resume: falls back to preserving the persisted RNG state)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Target database path (default: an auto-generated timestamped path under data/)",
    )
    return parser.parse_args(argv)


def _default_db_path() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"data/evoconnect4_{timestamp}.db"


def _is_resume(repo: Repository) -> bool:
    return len(repo.list_agents(status="alive")) > 0


def _normalize(value):
    return list(value) if isinstance(value, (list, tuple)) else value


def _mutable_config_dict(config: Config) -> dict:
    return {field: getattr(config, field) for field in MUTABLE_FIELDS}


def _validate_frozen_config(config: Config, stored: dict) -> None:
    mismatches = {}
    for field in FROZEN_FIELDS:
        live_value = _normalize(getattr(config, field))
        stored_value = _normalize(stored[field])
        if live_value != stored_value:
            mismatches[field] = (stored_value, live_value)
    if mismatches:
        raise FrozenConfigMismatch(mismatches)


def _persist_state(repo: Repository, population: Population) -> None:
    repo.upsert_simulation_state(
        current_tick=population.tick,
        rng_state=json.dumps(population.rng.bit_generator.state),
    )


def _run_fresh(config: Config, repo: Repository, ticks: int, seed: int | None) -> None:
    resolved_seed = seed if seed is not None else config.random_seed
    simulation_id = str(uuid.uuid4())
    population = Population(config, repo, rng=np.random.default_rng(resolved_seed))
    population.initialize()

    repo.insert_simulation_config(
        simulation_id=simulation_id,
        board_columns=config.board_columns,
        board_rows=config.board_rows,
        hidden_layer_sizes=config.hidden_layer_sizes,
        weight_init_std=config.weight_init_std,
    )
    initial_history = _mutable_config_dict(config)
    initial_history["random_seed"] = resolved_seed
    repo.insert_simulation_config_history_row(tick=0, **initial_history)
    _persist_state(repo, population)
    repo.commit()

    for _ in range(ticks):
        population.run_tick()
        _persist_state(repo, population)
        repo.commit()


def _run_resume(config: Config, repo: Repository, ticks: int, seed: int | None) -> None:
    stored_config = repo.get_simulation_config()
    if stored_config is None:
        raise CorruptDatabaseError(
            "Cannot resume: database contains alive agents but no simulation_config record "
            "(corrupt or foreign database)."
        )
    _validate_frozen_config(config, stored_config)

    population, persisted_rng_state = Population.load(config, repo)
    resume_tick = population.tick

    if seed is not None:
        population.rng = np.random.default_rng(seed)
        new_row = _mutable_config_dict(config)
        new_row["random_seed"] = seed
        repo.insert_simulation_config_history_row(tick=resume_tick, **new_row)
    else:
        previous = repo.get_effective_config_at_tick(resume_tick)
        if previous is None:
            raise CorruptDatabaseError(
                "Cannot resume: database contains alive agents but no simulation_config_history "
                "record (corrupt or foreign database)."
            )
        rng = np.random.default_rng()
        rng.bit_generator.state = json.loads(persisted_rng_state)
        population.rng = rng

        current = _mutable_config_dict(config)
        if any(current[field] != previous[field] for field in _MUTABLE_FIELDS_EXCLUDING_SEED):
            new_row = dict(current)
            new_row["random_seed"] = previous["random_seed"]  # not touched by this resume
            repo.insert_simulation_config_history_row(tick=resume_tick, **new_row)

    repo.commit()

    for _ in range(ticks):
        population.run_tick()
        _persist_state(repo, population)
        repo.commit()


def run(*, ticks: int, seed: int | None, db_path: str, config: Config | None = None) -> None:
    """Run (or resume) a simulation for `ticks` further ticks against `db_path`."""
    config = config if config is not None else load_config()

    db_file = Path(db_path)
    if db_file.parent != Path("."):
        db_file.parent.mkdir(parents=True, exist_ok=True)

    repo = Repository(str(db_file))
    try:
        if _is_resume(repo):
            _run_resume(config, repo, ticks, seed)
        else:
            _run_fresh(config, repo, ticks, seed)
    finally:
        repo.close()


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    db_path = args.db if args.db is not None else _default_db_path()

    try:
        run(ticks=args.ticks, seed=args.seed, db_path=db_path)
    except SimulationLifecycleError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
