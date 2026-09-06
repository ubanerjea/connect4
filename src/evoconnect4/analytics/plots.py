"""Chart generation from a single run's database (plan Sec9, Phase 7).

Each chart is a data-extraction function (plain data, unit-testable) paired
with a rendering function (matplotlib/pandas, covered only by a smoke test).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from evoconnect4.storage.repository import Repository

_ROLLING_WINDOW = 5


def fitness_over_time(repo: Repository) -> list[tuple[int, float, float, float]]:
    return [
        (s["tick"], s["avg_fitness"], s["max_fitness"], s["min_fitness"])
        for s in repo.list_snapshots()
    ]


def population_size_over_time(repo: Repository) -> list[tuple[int, int]]:
    return [(s["tick"], s["population_size"]) for s in repo.list_snapshots()]


def gene_drift_over_time(repo: Repository) -> list[tuple[int, float, float]]:
    return [(s["tick"], s["avg_lifespan"], s["avg_mutation_rate"]) for s in repo.list_snapshots()]


def benchmark_win_rate_over_time(repo: Repository) -> list[tuple[int, str, float]]:
    return sorted(
        (r["tick"], r["opponent_type"], r["win_rate"]) for r in repo.list_benchmark_results()
    )


def plot_fitness_over_time(data: list[tuple[int, float, float, float]], out_path: str) -> None:
    fig, ax = plt.subplots()
    if data:
        ticks = [d[0] for d in data]
        avg = pd.Series([d[1] for d in data], index=ticks)
        max_ = [d[2] for d in data]
        min_ = [d[3] for d in data]
        ax.plot(ticks, avg, label="avg fitness (raw)", alpha=0.4)
        ax.plot(ticks, avg.rolling(_ROLLING_WINDOW, min_periods=1).mean(), label="avg fitness (rolling)")
        ax.plot(ticks, max_, label="max fitness", linestyle="--")
        ax.plot(ticks, min_, label="min fitness", linestyle="--")
        ax.legend()
    ax.set_xlabel("tick")
    ax.set_ylabel("fitness")
    ax.set_title("Population fitness over time")
    fig.savefig(out_path)
    plt.close(fig)


def plot_population_size_over_time(data: list[tuple[int, int]], out_path: str) -> None:
    fig, ax = plt.subplots()
    if data:
        ax.plot([d[0] for d in data], [d[1] for d in data])
    ax.set_xlabel("tick")
    ax.set_ylabel("population size")
    ax.set_title("Population size over time")
    fig.savefig(out_path)
    plt.close(fig)


def plot_gene_drift_over_time(data: list[tuple[int, float, float]], out_path: str) -> None:
    fig, ax = plt.subplots()
    ax2 = ax.twinx()
    if data:
        ticks = [d[0] for d in data]
        lifespan_line = ax.plot(ticks, [d[1] for d in data], label="avg lifespan", color="tab:blue")
        mutation_line = ax2.plot(ticks, [d[2] for d in data], label="avg mutation rate", color="tab:orange")
        ax.legend(handles=lifespan_line + mutation_line)
    ax.set_xlabel("tick")
    ax.set_ylabel("avg lifespan")
    ax2.set_ylabel("avg mutation rate")
    ax.set_title("Gene drift over time")
    fig.savefig(out_path)
    plt.close(fig)


def plot_benchmark_win_rate_over_time(data: list[tuple[int, str, float]], out_path: str) -> None:
    fig, ax = plt.subplots()
    opponent_types = sorted({d[1] for d in data})
    for opponent_type in opponent_types:
        series = [(tick, wr) for tick, ot, wr in data if ot == opponent_type]
        ticks = [s[0] for s in series]
        win_rates = pd.Series([s[1] for s in series], index=ticks)
        ax.plot(ticks, win_rates, label=f"{opponent_type} (raw)", alpha=0.4)
        ax.plot(
            ticks,
            win_rates.rolling(_ROLLING_WINDOW, min_periods=1).mean(),
            label=f"{opponent_type} (rolling)",
        )
    if opponent_types:
        ax.legend()
    ax.set_xlabel("tick")
    ax.set_ylabel("win rate")
    ax.set_title("Benchmark win rate over time")
    fig.savefig(out_path)
    plt.close(fig)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate charts from a single EvoConnect4 run database.")
    parser.add_argument("--db", type=str, required=True, help="Path to the run's database file")
    parser.add_argument("--out-dir", type=str, required=True, help="Directory to write chart PNGs into")
    return parser.parse_args(argv)


def generate_all_charts(db_path: str, out_dir: str) -> None:
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    repo = Repository(db_path)
    try:
        plot_fitness_over_time(fitness_over_time(repo), str(out_dir_path / "fitness_over_time.png"))
        plot_population_size_over_time(
            population_size_over_time(repo), str(out_dir_path / "population_size_over_time.png")
        )
        plot_gene_drift_over_time(gene_drift_over_time(repo), str(out_dir_path / "gene_drift_over_time.png"))
        plot_benchmark_win_rate_over_time(
            benchmark_win_rate_over_time(repo), str(out_dir_path / "benchmark_win_rate_over_time.png")
        )
    finally:
        repo.close()


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    generate_all_charts(args.db, args.out_dir)


if __name__ == "__main__":
    main()
