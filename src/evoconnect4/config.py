"""Typed configuration loaded from config.yaml (plan §10)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "config.yaml"


@dataclass(frozen=True)
class Config:
    population_size: int

    board_columns: int
    board_rows: int

    hidden_layer_sizes: list[int]
    weight_init_std: float

    lifespan_range: tuple[int, int]
    lifespan_mutation_scale: float

    mutation_rate_range: tuple[float, float]
    mutation_rate_tau: float

    crossover_rate_range: tuple[float, float]
    crossover_rate_mutation_std: float

    tournament_size: int

    reproduction_interval_min: int
    reproduction_interval_max: int

    games_per_pair_per_tick: int

    cull_fraction_range: tuple[float, float]
    cull_fraction_beta_a: float
    cull_fraction_beta_b: float
    cull_allow_immature_offspring: bool

    benchmark_every_n_ticks: int
    benchmark_games_per_opponent: int

    random_seed: int


def load_config(path: Path | str = _DEFAULT_CONFIG_PATH) -> Config:
    """Load and parse config.yaml into a typed Config instance."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    return Config(
        population_size=raw["population_size"],
        board_columns=raw["board_columns"],
        board_rows=raw["board_rows"],
        hidden_layer_sizes=raw["hidden_layer_sizes"],
        weight_init_std=raw["weight_init_std"],
        lifespan_range=tuple(raw["lifespan_range"]),
        lifespan_mutation_scale=raw["lifespan_mutation_scale"],
        mutation_rate_range=tuple(raw["mutation_rate_range"]),
        mutation_rate_tau=raw["mutation_rate_tau"],
        crossover_rate_range=tuple(raw["crossover_rate_range"]),
        crossover_rate_mutation_std=raw["crossover_rate_mutation_std"],
        tournament_size=raw["tournament_size"],
        reproduction_interval_min=raw["reproduction_interval_min"],
        reproduction_interval_max=raw["reproduction_interval_max"],
        games_per_pair_per_tick=raw["games_per_pair_per_tick"],
        cull_fraction_range=tuple(raw["cull_fraction_range"]),
        cull_fraction_beta_a=raw["cull_fraction_beta_a"],
        cull_fraction_beta_b=raw["cull_fraction_beta_b"],
        cull_allow_immature_offspring=raw["cull_allow_immature_offspring"],
        benchmark_every_n_ticks=raw["benchmark_every_n_ticks"],
        benchmark_games_per_opponent=raw["benchmark_games_per_opponent"],
        random_seed=raw["random_seed"],
    )
