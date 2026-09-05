import numpy as np

from evoconnect4.agent.genome import decode, encode, random_genome
from evoconnect4.config import load_config
from evoconnect4.storage.repository import Repository

CONFIG = load_config()


def _repo() -> Repository:
    return Repository(":memory:")


def _insert_agent(repo: Repository, **overrides) -> int:
    fields = dict(
        parent1_id=None,
        parent2_id=None,
        generation=0,
        birth_tick=0,
        status="alive",
        nn_weights=[0.1, 0.2, 0.3],
        nn_architecture=[24],
        lifespan=100,
        mutation_rate=0.1,
        crossover_rate=0.5,
    )
    fields.update(overrides)
    return repo.insert_agent(**fields)


# -- 2.1 Repository core -------------------------------------------------


def test_repository_creates_schema_on_open():
    repo = _repo()
    tables = {
        row[0]
        for row in repo.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"agents", "games", "population_snapshots", "benchmark_results"} <= tables


# -- 3.1 insert_agent / round trip ---------------------------------------


def test_insert_agent_round_trips_all_fields():
    repo = _repo()
    agent_id = _insert_agent(repo)
    record = repo.get_agent(agent_id)

    assert record["agent_id"] == agent_id
    assert record["parent1_id"] is None
    assert record["generation"] == 0
    assert record["birth_tick"] == 0
    assert record["status"] == "alive"
    assert record["nn_weights"] == [0.1, 0.2, 0.3]
    assert record["nn_architecture"] == [24]
    assert record["lifespan"] == 100
    assert record["mutation_rate"] == 0.1
    assert record["crossover_rate"] == 0.5


def test_insert_agent_round_trips_genome_data():
    repo = _repo()
    genome = random_genome(CONFIG, rng=np.random.default_rng(1))
    encoded = encode(genome)

    agent_id = _insert_agent(
        repo,
        nn_weights=encoded["weights"],
        nn_architecture=encoded["hidden_layer_sizes"],
        lifespan=genome.lifespan,
        mutation_rate=genome.mutation_rate,
        crossover_rate=genome.crossover_rate,
    )
    record = repo.get_agent(agent_id)

    restored = decode(
        {
            "weights": record["nn_weights"],
            "hidden_layer_sizes": record["nn_architecture"],
            "lifespan": record["lifespan"],
            "mutation_rate": record["mutation_rate"],
            "crossover_rate": record["crossover_rate"],
        }
    )
    assert np.array_equal(restored.weights, genome.weights)
    assert restored.hidden_layer_sizes == genome.hidden_layer_sizes


# -- 3.2 get_agent --------------------------------------------------------


def test_get_agent_returns_none_for_nonexistent_id():
    repo = _repo()
    assert repo.get_agent(999) is None


# -- 3.3 update_agent_stats ------------------------------------------------


def test_update_agent_stats_persists():
    repo = _repo()
    agent_id = _insert_agent(repo)

    repo.update_agent_stats(
        agent_id,
        games_played=10,
        wins=6,
        losses=3,
        draws=1,
        fitness=0.65,
        games_since_last_reproduction=4,
    )
    record = repo.get_agent(agent_id)

    assert record["games_played"] == 10
    assert record["wins"] == 6
    assert record["losses"] == 3
    assert record["draws"] == 1
    assert record["fitness"] == 0.65
    assert record["games_since_last_reproduction"] == 4


# -- 3.4 mark_agent_dead ----------------------------------------------------


def test_mark_agent_dead_persists():
    repo = _repo()
    agent_id = _insert_agent(repo)

    repo.mark_agent_dead(agent_id, death_tick=42, death_cause="old_age")
    record = repo.get_agent(agent_id)

    assert record["status"] == "dead"
    assert record["death_tick"] == 42
    assert record["death_cause"] == "old_age"


# -- 3.5 list_agents --------------------------------------------------------


def test_list_agents_filters_by_status():
    repo = _repo()
    alive_id = _insert_agent(repo)
    dead_id = _insert_agent(repo)
    repo.mark_agent_dead(dead_id, death_tick=1, death_cause="culled")

    alive = repo.list_agents(status="alive")
    ids = {a["agent_id"] for a in alive}

    assert alive_id in ids
    assert dead_id not in ids


# -- 4.1 insert_game / round trip -------------------------------------------


def test_insert_game_round_trips_all_fields():
    repo = _repo()
    p1 = _insert_agent(repo)
    p2 = _insert_agent(repo)

    game_id = repo.insert_game(
        tick=5,
        player1_agent_id=p1,
        player2_agent_id=p2,
        result="player1_win",
        num_moves=13,
        move_history=[3, 3, 2, 4, 3],
        game_type="evolution",
    )
    record = repo.get_game(game_id)

    assert record["game_id"] == game_id
    assert record["tick"] == 5
    assert record["player1_agent_id"] == p1
    assert record["player2_agent_id"] == p2
    assert record["result"] == "player1_win"
    assert record["num_moves"] == 13
    assert record["move_history"] == [3, 3, 2, 4, 3]
    assert record["game_type"] == "evolution"


# -- 4.2 get_game -----------------------------------------------------------


def test_get_game_returns_none_for_nonexistent_id():
    repo = _repo()
    assert repo.get_game(999) is None


# -- 4.3 list_games -----------------------------------------------------------


def test_list_games_filters_by_tick():
    repo = _repo()
    p1 = _insert_agent(repo)
    p2 = _insert_agent(repo)

    game_tick_1 = repo.insert_game(
        tick=1, player1_agent_id=p1, player2_agent_id=p2, result="draw",
        num_moves=42, move_history=[], game_type="evolution",
    )
    repo.insert_game(
        tick=2, player1_agent_id=p1, player2_agent_id=p2, result="draw",
        num_moves=42, move_history=[], game_type="evolution",
    )

    tick_1_games = repo.list_games(tick=1)
    assert {g["game_id"] for g in tick_1_games} == {game_tick_1}


# -- 5.1 insert_snapshot / round trip -----------------------------------------


def test_insert_snapshot_round_trips_all_fields():
    repo = _repo()
    best = _insert_agent(repo)

    snapshot_id = repo.insert_snapshot(
        tick=10,
        population_size=100,
        avg_fitness=0.5,
        max_fitness=0.9,
        min_fitness=0.1,
        avg_lifespan=120.0,
        avg_mutation_rate=0.15,
        best_agent_id=best,
    )
    record = repo.get_latest_snapshot()

    assert record["snapshot_id"] == snapshot_id
    assert record["tick"] == 10
    assert record["population_size"] == 100
    assert record["avg_fitness"] == 0.5
    assert record["max_fitness"] == 0.9
    assert record["min_fitness"] == 0.1
    assert record["avg_lifespan"] == 120.0
    assert record["avg_mutation_rate"] == 0.15
    assert record["best_agent_id"] == best


# -- 5.2 get_latest_snapshot -----------------------------------------------


def test_get_latest_snapshot_returns_highest_tick():
    repo = _repo()
    best = _insert_agent(repo)
    kwargs = dict(
        population_size=100, avg_fitness=0.5, max_fitness=0.9, min_fitness=0.1,
        avg_lifespan=120.0, avg_mutation_rate=0.15, best_agent_id=best,
    )

    repo.insert_snapshot(tick=1, **kwargs)
    latest_id = repo.insert_snapshot(tick=5, **kwargs)
    repo.insert_snapshot(tick=3, **kwargs)

    latest = repo.get_latest_snapshot()
    assert latest["snapshot_id"] == latest_id
    assert latest["tick"] == 5


def test_get_latest_snapshot_returns_none_when_empty():
    repo = _repo()
    assert repo.get_latest_snapshot() is None


# -- 6.1 parent_avg_fitness round trip --------------------------------------


def test_insert_agent_round_trips_parent_avg_fitness():
    repo = _repo()
    agent_id = _insert_agent(repo, parent_avg_fitness=0.73)
    record = repo.get_agent(agent_id)
    assert record["parent_avg_fitness"] == 0.73


def test_insert_agent_defaults_parent_avg_fitness_to_zero():
    repo = _repo()
    agent_id = _insert_agent(repo)
    record = repo.get_agent(agent_id)
    assert record["parent_avg_fitness"] == 0.0


# -- 6.2 simulation_config round trip ----------------------------------------


def test_insert_simulation_config_round_trips():
    repo = _repo()
    repo.insert_simulation_config(
        simulation_id="sim-abc",
        board_columns=7,
        board_rows=6,
        hidden_layer_sizes=[24],
        weight_init_std=0.5,
    )
    record = repo.get_simulation_config()

    assert record["simulation_id"] == "sim-abc"
    assert record["board_columns"] == 7
    assert record["board_rows"] == 6
    assert record["hidden_layer_sizes"] == [24]
    assert record["weight_init_std"] == 0.5


def test_get_simulation_config_returns_none_when_empty():
    repo = _repo()
    assert repo.get_simulation_config() is None


# -- 6.3 simulation_config_history -------------------------------------------


def _history_kwargs(**overrides) -> dict:
    fields = dict(
        tick=0,
        population_size=100,
        lifespan_range=(50, 150),
        lifespan_mutation_scale=0.1,
        mutation_rate_range=(0.01, 0.5),
        mutation_rate_tau=0.15,
        crossover_rate_range=(0.0, 1.0),
        crossover_rate_mutation_std=0.05,
        tournament_size=5,
        reproduction_interval_min=8,
        reproduction_interval_max=25,
        games_per_pair_per_tick=2,
        benchmark_every_n_ticks=10,
        benchmark_games_per_opponent=20,
        random_seed=42,
        cull_fraction_range=(0.1, 0.5),
        cull_fraction_beta_a=1.0,
        cull_fraction_beta_b=1.0,
        cull_allow_immature_offspring=False,
    )
    fields.update(overrides)
    return fields


def test_effective_config_at_tick_returns_initial_row():
    repo = _repo()
    repo.insert_simulation_config_history_row(**_history_kwargs(tick=0, tournament_size=5))

    record = repo.get_effective_config_at_tick(100)
    assert record["tournament_size"] == 5
    assert record["lifespan_range"] == (50, 150)
    assert record["cull_allow_immature_offspring"] is False


def test_effective_config_at_tick_ignores_later_rows_for_earlier_ticks():
    repo = _repo()
    repo.insert_simulation_config_history_row(**_history_kwargs(tick=0, tournament_size=5))
    repo.insert_simulation_config_history_row(**_history_kwargs(tick=250, tournament_size=8))

    assert repo.get_effective_config_at_tick(100)["tournament_size"] == 5
    assert repo.get_effective_config_at_tick(300)["tournament_size"] == 8


# -- 6.4 simulation_state upsert ---------------------------------------------


def test_simulation_state_upsert_keeps_only_latest_values():
    repo = _repo()
    repo.upsert_simulation_state(current_tick=5, rng_state='{"a": 1}')
    repo.upsert_simulation_state(current_tick=6, rng_state='{"a": 2}')

    record = repo.get_simulation_state()
    assert record["current_tick"] == 6
    assert record["rng_state"] == '{"a": 2}'


def test_get_simulation_state_returns_none_when_empty():
    repo = _repo()
    assert repo.get_simulation_state() is None
