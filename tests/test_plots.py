import dataclasses

from evoconnect4.analytics.plots import (
    benchmark_win_rate_over_time,
    fitness_over_time,
    gene_drift_over_time,
    generate_all_charts,
    plot_benchmark_win_rate_over_time,
    plot_fitness_over_time,
    plot_gene_drift_over_time,
    plot_population_size_over_time,
    population_size_over_time,
)
from evoconnect4.config import load_config
from evoconnect4.storage.repository import Repository

BASE_CONFIG = load_config()


def _test_config(**overrides):
    return dataclasses.replace(BASE_CONFIG, **overrides)


def _insert_agent(repo: Repository) -> int:
    return repo.insert_agent(
        parent1_id=None, parent2_id=None, generation=0, birth_tick=0, status="alive",
        nn_weights=[0.1], nn_architecture=[24], lifespan=100, mutation_rate=0.1, crossover_rate=0.5,
    )


# -- 1.1 fitness_over_time -----------------------------------------------------


def test_fitness_over_time_matches_inserted_snapshots():
    repo = Repository(":memory:")
    best = _insert_agent(repo)
    repo.insert_snapshot(
        tick=1, population_size=10, avg_fitness=0.3, max_fitness=0.6, min_fitness=0.1,
        avg_lifespan=100.0, avg_mutation_rate=0.2, best_agent_id=best,
    )
    repo.insert_snapshot(
        tick=2, population_size=10, avg_fitness=0.4, max_fitness=0.7, min_fitness=0.15,
        avg_lifespan=101.0, avg_mutation_rate=0.19, best_agent_id=best,
    )

    data = fitness_over_time(repo)

    assert data == [(1, 0.3, 0.6, 0.1), (2, 0.4, 0.7, 0.15)]


def test_fitness_over_time_returns_empty_list_when_no_snapshots():
    repo = Repository(":memory:")
    assert fitness_over_time(repo) == []


# -- 1.2 population_size_over_time ----------------------------------------------


def test_population_size_over_time_matches_inserted_snapshots():
    repo = Repository(":memory:")
    best = _insert_agent(repo)
    repo.insert_snapshot(
        tick=1, population_size=42, avg_fitness=0.3, max_fitness=0.6, min_fitness=0.1,
        avg_lifespan=100.0, avg_mutation_rate=0.2, best_agent_id=best,
    )

    assert population_size_over_time(repo) == [(1, 42)]


# -- 1.3 gene_drift_over_time --------------------------------------------------


def test_gene_drift_over_time_matches_inserted_snapshots():
    repo = Repository(":memory:")
    best = _insert_agent(repo)
    repo.insert_snapshot(
        tick=1, population_size=10, avg_fitness=0.3, max_fitness=0.6, min_fitness=0.1,
        avg_lifespan=88.0, avg_mutation_rate=0.25, best_agent_id=best,
    )

    assert gene_drift_over_time(repo) == [(1, 88.0, 0.25)]


# -- 1.4 benchmark_win_rate_over_time --------------------------------------------


def test_benchmark_win_rate_over_time_matches_inserted_results():
    repo = Repository(":memory:")
    agent_id = _insert_agent(repo)
    repo.insert_benchmark_result(tick=10, agent_id=agent_id, opponent_type="random", games_played=20, win_rate=0.5)
    repo.insert_benchmark_result(tick=10, agent_id=agent_id, opponent_type="heuristic", games_played=20, win_rate=0.2)

    data = benchmark_win_rate_over_time(repo)

    assert data == [(10, "heuristic", 0.2), (10, "random", 0.5)]


# -- 2.1 rendering smoke tests --------------------------------------------------


def test_plot_fitness_over_time_produces_nonzero_png(tmp_path):
    out_path = tmp_path / "fitness.png"
    plot_fitness_over_time([(1, 0.3, 0.6, 0.1), (2, 0.4, 0.7, 0.15)], str(out_path))
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_fitness_over_time_handles_empty_data(tmp_path):
    out_path = tmp_path / "fitness_empty.png"
    plot_fitness_over_time([], str(out_path))
    assert out_path.exists()


def test_plot_population_size_over_time_produces_nonzero_png(tmp_path):
    out_path = tmp_path / "size.png"
    plot_population_size_over_time([(1, 10), (2, 12)], str(out_path))
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_gene_drift_over_time_produces_nonzero_png(tmp_path):
    out_path = tmp_path / "drift.png"
    plot_gene_drift_over_time([(1, 100.0, 0.2), (2, 101.0, 0.19)], str(out_path))
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_benchmark_win_rate_over_time_produces_nonzero_png(tmp_path):
    out_path = tmp_path / "benchmark.png"
    plot_benchmark_win_rate_over_time([(10, "random", 0.5), (20, "random", 0.6)], str(out_path))
    assert out_path.exists()
    assert out_path.stat().st_size > 0


# -- 2.2 CLI integration ---------------------------------------------------------


def test_generate_all_charts_writes_four_nonzero_files(tmp_path):
    db_path = str(tmp_path / "run.db")
    out_dir = tmp_path / "charts"

    repo = Repository(db_path)
    best = _insert_agent(repo)
    repo.insert_snapshot(
        tick=1, population_size=10, avg_fitness=0.3, max_fitness=0.6, min_fitness=0.1,
        avg_lifespan=100.0, avg_mutation_rate=0.2, best_agent_id=best,
    )
    repo.insert_benchmark_result(tick=1, agent_id=best, opponent_type="random", games_played=10, win_rate=0.4)
    repo.commit()
    repo.close()

    generate_all_charts(db_path, str(out_dir))

    expected = [
        "fitness_over_time.png",
        "population_size_over_time.png",
        "gene_drift_over_time.png",
        "benchmark_win_rate_over_time.png",
    ]
    for filename in expected:
        path = out_dir / filename
        assert path.exists(), f"missing {filename}"
        assert path.stat().st_size > 0


def test_generate_all_charts_creates_missing_output_dir(tmp_path):
    db_path = str(tmp_path / "run.db")
    out_dir = tmp_path / "nested" / "charts"

    Repository(db_path).close()

    generate_all_charts(db_path, str(out_dir))

    assert out_dir.exists()
    assert (out_dir / "fitness_over_time.png").exists()
