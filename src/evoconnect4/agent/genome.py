"""Genome: random init, encode/decode, mutate, crossover (plan Sec3).

Genome is the germline -- created at random, or by combining/mutating a
parent's germline. It is never touched by anything an agent does during
its own life (that's the plan's future somatic-mutation/senescence idea,
Sec4.7, deliberately not built here).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from evoconnect4.agent.network import weight_count
from evoconnect4.config import Config


@dataclass(frozen=True)
class Genome:
    weights: np.ndarray
    hidden_layer_sizes: list[int]
    lifespan: int
    mutation_rate: float
    crossover_rate: float


def _architecture(config: Config) -> tuple[int, int, int]:
    input_size = config.board_columns * config.board_rows
    hidden_size = config.hidden_layer_sizes[0]
    output_size = config.board_columns
    return input_size, hidden_size, output_size


def _random_weights(rng: np.random.Generator, input_size: int, hidden_size: int, output_size: int, std: float) -> np.ndarray:
    weights = rng.normal(0.0, std, size=weight_count(input_size, hidden_size, output_size))
    i = input_size * hidden_size
    weights[i:i + hidden_size] = 0.0  # b1
    i += hidden_size + hidden_size * output_size
    weights[i:i + output_size] = 0.0  # b2
    return weights


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def random_genome(config: Config, rng: np.random.Generator | None = None) -> Genome:
    rng = rng if rng is not None else np.random.default_rng()
    input_size, hidden_size, output_size = _architecture(config)

    weights = _random_weights(rng, input_size, hidden_size, output_size, config.weight_init_std)
    lifespan_min, lifespan_max = config.lifespan_range
    mutation_min, mutation_max = config.mutation_rate_range
    crossover_min, crossover_max = config.crossover_rate_range

    return Genome(
        weights=weights,
        hidden_layer_sizes=list(config.hidden_layer_sizes),
        lifespan=int(rng.integers(lifespan_min, lifespan_max + 1)),
        mutation_rate=float(rng.uniform(mutation_min, mutation_max)),
        crossover_rate=float(rng.uniform(crossover_min, crossover_max)),
    )


def encode(genome: Genome) -> dict:
    return {
        "weights": genome.weights.tolist(),
        "hidden_layer_sizes": list(genome.hidden_layer_sizes),
        "lifespan": genome.lifespan,
        "mutation_rate": genome.mutation_rate,
        "crossover_rate": genome.crossover_rate,
    }


def decode(data: dict) -> Genome:
    return Genome(
        weights=np.array(data["weights"], dtype=float),
        hidden_layer_sizes=list(data["hidden_layer_sizes"]),
        lifespan=data["lifespan"],
        mutation_rate=data["mutation_rate"],
        crossover_rate=data["crossover_rate"],
    )


def mutate(genome: Genome, config: Config, rng: np.random.Generator | None = None) -> Genome:
    rng = rng if rng is not None else np.random.default_rng()
    mutation_min, mutation_max = config.mutation_rate_range
    lifespan_min, lifespan_max = config.lifespan_range
    crossover_min, crossover_max = config.crossover_rate_range

    # Self-adaptive step: mutate the strategy parameter (sigma) first, then
    # use the *new* sigma to perturb the object parameters (weights) --
    # standard self-adaptive evolution-strategies convention.
    new_mutation_rate = _clamp(
        genome.mutation_rate * float(np.exp(rng.normal(0.0, config.mutation_rate_tau))),
        mutation_min,
        mutation_max,
    )
    new_weights = genome.weights + rng.normal(0.0, new_mutation_rate, size=genome.weights.shape)

    new_lifespan = round(genome.lifespan * (1.0 + rng.normal(0.0, config.lifespan_mutation_scale)))
    new_lifespan = int(_clamp(new_lifespan, lifespan_min, lifespan_max))

    new_crossover_rate = _clamp(
        genome.crossover_rate + rng.normal(0.0, config.crossover_rate_mutation_std),
        crossover_min,
        crossover_max,
    )

    return replace(
        genome,
        weights=new_weights,
        lifespan=new_lifespan,
        mutation_rate=new_mutation_rate,
        crossover_rate=new_crossover_rate,
    )


def crossover(genome_a: Genome, genome_b: Genome, rng: np.random.Generator | None = None) -> Genome:
    rng = rng if rng is not None else np.random.default_rng()

    from_a = rng.integers(0, 2, size=genome_a.weights.shape).astype(bool)
    child_weights = np.where(from_a, genome_a.weights, genome_b.weights)

    return Genome(
        weights=child_weights,
        hidden_layer_sizes=list(genome_a.hidden_layer_sizes),
        lifespan=round((genome_a.lifespan + genome_b.lifespan) / 2),
        mutation_rate=(genome_a.mutation_rate + genome_b.mutation_rate) / 2,
        crossover_rate=(genome_a.crossover_rate + genome_b.crossover_rate) / 2,
    )
