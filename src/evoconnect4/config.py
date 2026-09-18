"""Typed configuration loaded from config.yaml (plan §10)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

    heuristic_games_per_agent_per_tick: int
    heuristic_survival_alpha: float

    heuristic_bot_level: str
    heuristic_fitness_weight_max: float
    heuristic_fitness_weight_min: float
    heuristic_weight_adapt_low: float
    heuristic_weight_adapt_high: float
    heuristic_weight_adapt_window: int

    hof_enabled: bool
    hof_max_size: int
    hof_games_per_agent_per_tick: int
    hof_maintenance_every_n_ticks: int
    hof_maintenance_heuristic_games: int
    hof_maintenance_peer_games: int
    hof_entry_heuristic_threshold: float
    hof_eviction_margin: float
    hof_fitness_weight_max: float

    random_seed: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Config":
        # backward compat: old key heuristic_fitness_weight → heuristic_fitness_weight_max
        if "heuristic_fitness_weight_max" not in raw and "heuristic_fitness_weight" in raw:
            raw = dict(raw)
            raw["heuristic_fitness_weight_max"] = raw["heuristic_fitness_weight"]

        return cls(
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
            heuristic_games_per_agent_per_tick=raw["heuristic_games_per_agent_per_tick"],
            heuristic_survival_alpha=raw["heuristic_survival_alpha"],
            heuristic_bot_level=raw.get("heuristic_bot_level", "tactical"),
            heuristic_fitness_weight_max=raw.get("heuristic_fitness_weight_max", 0.7),
            heuristic_fitness_weight_min=raw.get("heuristic_fitness_weight_min", 0.3),
            heuristic_weight_adapt_low=raw.get("heuristic_weight_adapt_low", 0.60),
            heuristic_weight_adapt_high=raw.get("heuristic_weight_adapt_high", 0.90),
            heuristic_weight_adapt_window=raw.get("heuristic_weight_adapt_window", 20),
            hof_enabled=raw.get("hof_enabled", True),
            hof_max_size=raw.get("hof_max_size", 20),
            hof_games_per_agent_per_tick=raw.get("hof_games_per_agent_per_tick", 2),
            hof_maintenance_every_n_ticks=raw.get("hof_maintenance_every_n_ticks", 50),
            hof_maintenance_heuristic_games=raw.get("hof_maintenance_heuristic_games", 20),
            hof_maintenance_peer_games=raw.get("hof_maintenance_peer_games", 4),
            hof_entry_heuristic_threshold=raw.get("hof_entry_heuristic_threshold", 0.70),
            hof_eviction_margin=raw.get("hof_eviction_margin", 0.15),
            hof_fitness_weight_max=raw.get("hof_fitness_weight_max", 0.4),
            random_seed=raw["random_seed"],
        )


def load_config(path: Path | str = _DEFAULT_CONFIG_PATH) -> Config:
    """Load and parse config.yaml into a typed Config instance."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config.from_dict(raw)
