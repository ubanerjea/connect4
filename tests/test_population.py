import dataclasses

import numpy as np

from evoconnect4.agent.genome import random_genome
from evoconnect4.config import load_config
from evoconnect4.evolution.population import Population, reproduction_interval
from evoconnect4.storage.repository import Repository

BASE_CONFIG = load_config()


def _test_config(**overrides):
    return dataclasses.replace(BASE_CONFIG, **overrides)


# -- 2.1 Population core --------------------------------------------------


def test_initialize_creates_population_size_agents():
    config = _test_config(population_size=10)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(1))

    pop.initialize()

    assert len(pop.alive) == 10
    db_agents = repo.list_agents(status="alive")
    assert len(db_agents) == 10
    for agent in pop.alive:
        assert agent.generation == 0
    for record in db_agents:
        assert record["parent1_id"] is None
        assert record["parent2_id"] is None
        assert record["generation"] == 0


# -- 3.1 Pairing -----------------------------------------------------------


def test_pairing_leaves_at_most_one_agent_unpaired_when_odd():
    config = _test_config(population_size=7)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(2))
    pop.initialize()

    pairs = pop._pair_alive()
    paired_ids = {id(a) for pair in pairs for a in pair}
    unpaired = [a for a in pop.alive if id(a) not in paired_ids]

    assert len(pairs) == 3
    assert len(unpaired) == 1


# -- 3.2 Games ---------------------------------------------------------------


def test_play_pair_records_two_games_with_move_history():
    config = _test_config(population_size=2)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(3))
    pop.initialize()
    a, b = pop.alive
    pop.tick = 1

    pop._play_pair(a, b)

    games = repo.list_games(tick=1)
    assert len(games) == 2
    for g in games:
        assert len(g["move_history"]) > 0


def test_play_pair_honors_games_per_pair_per_tick():
    import evoconnect4.evolution.population as pop_module

    config = _test_config(population_size=2, games_per_pair_per_tick=4)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(3))
    pop.initialize()
    a, b = pop.alive
    pop.tick = 1

    first_movers_seen = []
    original_play_match = pop_module.play_match

    def spy_play_match(chooser1, chooser2, *, first_mover):
        first_movers_seen.append(first_mover)
        return original_play_match(chooser1, chooser2, first_mover=first_mover)

    pop_module.play_match = spy_play_match
    try:
        pop._play_pair(a, b)
    finally:
        pop_module.play_match = original_play_match

    games = repo.list_games(tick=1)
    assert len(games) == 4
    # first_mover alternates by game index: even=1, odd=-1
    assert first_movers_seen == [1, -1, 1, -1]


# -- 4.1 Stats -----------------------------------------------------------------


def test_game_stats_are_updated_in_memory_and_persisted():
    config = _test_config(population_size=2)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(4))
    pop.initialize()

    pop.run_tick()

    for agent in pop.alive:
        assert agent.games_played == 2
        record = repo.get_agent(agent.agent_id)
        assert record["games_played"] == 2
        assert record["wins"] == agent.wins
        assert record["losses"] == agent.losses
        assert record["draws"] == agent.draws


# -- 4.2 Fitness -----------------------------------------------------------------


def test_fitness_recomputed_matches_formula():
    config = _test_config(population_size=2)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(5))
    pop.initialize()

    pop.run_tick()

    for agent in pop.alive:
        expected = (agent.wins + 0.5 * agent.draws) / agent.games_played
        assert np.isclose(agent.fitness, expected)
        record = repo.get_agent(agent.agent_id)
        assert np.isclose(record["fitness"], expected)


# -- 5.1 Reproduction interval -----------------------------------------------------


def test_reproduction_interval_shorter_for_higher_fitness():
    config = _test_config()
    low_fitness_interval = reproduction_interval(0.0, config)
    high_fitness_interval = reproduction_interval(1.0, config)

    assert high_fitness_interval <= low_fitness_interval
    assert low_fitness_interval == config.reproduction_interval_max
    assert high_fitness_interval == config.reproduction_interval_min


# -- 5.2 / 5.3 Reproduction -----------------------------------------------------


def test_reproduce_clone_path_produces_single_parent_child():
    config = _test_config(population_size=3)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(6))
    pop.initialize()
    parent = pop.alive[0]
    parent.genome = dataclasses.replace(parent.genome, crossover_rate=0.0)
    before_count = len(pop.alive)

    pop._reproduce(parent)

    assert len(pop.alive) == before_count + 1
    child = pop.alive[-1]
    record = repo.get_agent(child.agent_id)
    assert record["parent1_id"] == parent.agent_id
    assert record["parent2_id"] is None


def test_reproduce_crossover_path_produces_two_parent_child():
    config = _test_config(population_size=3)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(7))
    pop.initialize()
    parent = pop.alive[0]
    parent.genome = dataclasses.replace(parent.genome, crossover_rate=1.0)

    pop._reproduce(parent)

    child = pop.alive[-1]
    record = repo.get_agent(child.agent_id)
    assert record["parent1_id"] == parent.agent_id
    assert record["parent2_id"] is not None
    assert record["parent2_id"] != parent.agent_id


def test_reproduce_resets_parent_games_since_last_reproduction():
    config = _test_config(population_size=3)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(8))
    pop.initialize()
    parent = pop.alive[0]
    parent.games_since_last_reproduction = 999

    pop._reproduce(parent)

    assert parent.games_since_last_reproduction == 0
    record = repo.get_agent(parent.agent_id)
    assert record["games_since_last_reproduction"] == 0


# -- 6.1 Death ------------------------------------------------------------------


def test_agent_dies_automatically_when_reaching_lifespan_via_tick():
    config = _test_config(population_size=2)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(10))
    pop.initialize()
    agent_ids = [a.agent_id for a in pop.alive]
    for agent in pop.alive:
        agent.genome = dataclasses.replace(agent.genome, lifespan=1)

    pop.run_tick()

    assert len(pop.alive) == 0
    for agent_id in agent_ids:
        record = repo.get_agent(agent_id)
        assert record["status"] == "dead"
        assert record["death_cause"] == "old_age"


# -- 7.1 Population cap ------------------------------------------------------------


def test_enforce_population_cap_culls_lowest_fitness_eligible_agent():
    # 3 alive, cap=2; fraction=0.4 → int(0.4*3)=1 → cull exactly 1 agent
    config = _test_config(population_size=2, cull_fraction_range=(0.4, 0.4))
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(11))
    pop.initialize()
    strong, weak = pop.alive[0], pop.alive[1]
    strong.games_played = config.reproduction_interval_min
    strong.fitness = 0.9
    weak.games_played = config.reproduction_interval_min
    weak.fitness = 0.1

    extra_genome = random_genome(config, rng=np.random.default_rng(99))
    young = pop._add_agent(extra_genome, parent1_id=None, parent2_id=None, generation=0)
    young.games_played = 0
    young.fitness = 0.0

    pop._enforce_population_cap()

    assert len(pop.alive) == 2
    assert strong in pop.alive
    assert young in pop.alive
    assert weak not in pop.alive
    record = repo.get_agent(weak.agent_id)
    assert record["status"] == "dead"
    assert record["death_cause"] == "culled"


# -- 7.2 Culling: distribution and tier-2 -----------------------------------------


def test_cull_count_falls_within_configured_fraction_range():
    frac_lo, frac_hi = 0.25, 0.75
    alive_count = 20
    n_trials = 200
    min_count = max(1, int(frac_lo * alive_count))
    max_count = int(frac_hi * alive_count)

    config = _test_config(
        population_size=10,
        cull_fraction_range=(frac_lo, frac_hi),
        reproduction_interval_min=0,
    )
    repo = Repository(":memory:")
    rng = np.random.default_rng(42)
    pop = Population(config, repo, rng=rng)
    agents = []
    for _ in range(alive_count):
        genome = random_genome(config, rng=rng)
        a = pop._add_agent(genome, parent1_id=None, parent2_id=None, generation=0)
        a.games_played = 0
        agents.append(a)

    counts = []
    for _ in range(n_trials):
        pop.alive = agents[:]
        before = len(pop.alive)
        pop._kill = lambda agent, *, cause: pop.alive.remove(agent)
        pop._enforce_population_cap()
        counts.append(before - len(pop.alive))

    for c in counts:
        assert min_count <= c <= max_count, f"count {c} outside [{min_count}, {max_count}]"


def test_cull_distribution_reflects_beta_shape():
    frac_lo, frac_hi = 0.25, 0.75
    alive_count = 20
    n_trials = 500

    def run_trials(beta_a, beta_b, seed):
        config = _test_config(
            population_size=10,
            cull_fraction_range=(frac_lo, frac_hi),
            cull_fraction_beta_a=beta_a,
            cull_fraction_beta_b=beta_b,
            reproduction_interval_min=0,
        )
        repo = Repository(":memory:")
        rng = np.random.default_rng(seed)
        pop = Population(config, repo, rng=rng)
        agents = []
        for _ in range(alive_count):
            genome = random_genome(config, rng=rng)
            a = pop._add_agent(genome, parent1_id=None, parent2_id=None, generation=0)
            a.games_played = 0
            agents.append(a)

        fractions = []
        for _ in range(n_trials):
            pop.alive = agents[:]
            before = len(pop.alive)
            pop._kill = lambda agent, *, cause: pop.alive.remove(agent)
            pop._enforce_population_cap()
            fractions.append((before - len(pop.alive)) / alive_count)
        return fractions

    fractions_bell = run_trials(5.0, 5.0, seed=100)
    fractions_uniform = run_trials(1.0, 1.0, seed=200)

    # Bell-shaped Beta(5,5) has lower variance than uniform Beta(1,1): samples
    # cluster more tightly around the midpoint, so std should be smaller.
    assert np.std(fractions_bell) < np.std(fractions_uniform)


def test_tier2_never_activates_when_flag_off():
    config = _test_config(
        population_size=5,
        cull_fraction_range=(1.0, 1.0),
        cull_allow_immature_offspring=False,
        reproduction_interval_min=10,
    )
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(42))

    for _ in range(7):
        genome = random_genome(config, rng=np.random.default_rng(1))
        a = pop._add_agent(genome, parent1_id=None, parent2_id=None, generation=0)
        a.games_played = 0  # immature: 0 < reproduction_interval_min=10

    assert len(pop.alive) == 7
    pop._enforce_population_cap()
    # No tier-1 candidates; tier-2 flag off → graceful under-fill, no agents removed
    assert len(pop.alive) == 7


def test_tier2_activates_after_tier1_exhausted():
    # 10 alive, cap=5, fraction=0.50 → count=5; 2 mature (tier-1 fills 2),
    # 8 immature (tier-2 fills 3) → 5 surviving immature agents
    config = _test_config(
        population_size=5,
        cull_fraction_range=(0.5, 0.5),
        cull_allow_immature_offspring=True,
        reproduction_interval_min=5,
    )
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(42))

    mature_agents = []
    for _ in range(2):
        genome = random_genome(config, rng=np.random.default_rng(1))
        a = pop._add_agent(genome, parent1_id=None, parent2_id=None, generation=0)
        a.games_played = config.reproduction_interval_min
        a.fitness = 0.5
        mature_agents.append(a)

    immature_paf_values = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    immature_agents = []
    for paf in immature_paf_values:
        genome = random_genome(config, rng=np.random.default_rng(2))
        a = pop._add_agent(genome, parent1_id=None, parent2_id=None, generation=0,
                           parent_avg_fitness=paf)
        a.games_played = 0  # immature
        immature_agents.append(a)

    assert len(pop.alive) == 10
    pop._enforce_population_cap()

    assert len(pop.alive) == 5
    # Both mature agents culled (all of tier-1)
    for a in mature_agents:
        assert a not in pop.alive
    # The 3 immature with lowest parent_avg_fitness (0.1, 0.2, 0.3) are culled
    for a in immature_agents:
        if a.parent_avg_fitness <= 0.3:
            assert a not in pop.alive
        else:
            assert a in pop.alive


def test_at_least_one_culled_when_triggered_and_candidate_exists():
    # int(0.01 * N) rounds to 0; max(..., 1) guarantees at least 1 culled
    config = _test_config(
        population_size=5,
        cull_fraction_range=(0.01, 0.01),
        reproduction_interval_min=0,
    )
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(42))

    for _ in range(6):  # one over capacity
        genome = random_genome(config, rng=np.random.default_rng(1))
        a = pop._add_agent(genome, parent1_id=None, parent2_id=None, generation=0)
        a.games_played = 0

    assert len(pop.alive) == 6
    pop._enforce_population_cap()
    assert len(pop.alive) == 5  # exactly 1 culled


# -- 8.1 Snapshot ------------------------------------------------------------------


def test_snapshot_written_matches_population_size():
    config = _test_config(population_size=4)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(12))
    pop.initialize()

    pop.run_tick()

    snapshot = repo.get_latest_snapshot()
    assert snapshot is not None
    assert snapshot["tick"] == 1
    assert snapshot["population_size"] == len(pop.alive)


# -- 9.1 Full tick -----------------------------------------------------------------


def test_run_tick_completes_without_error():
    config = _test_config(population_size=6)
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(13))
    pop.initialize()

    pop.run_tick()

    assert pop.tick == 1


# -- 9.2 Phase 4 DoD: 50-tick run ---------------------------------------------------


def test_fifty_tick_run_shows_plausible_dynamics_and_no_runaway_size():
    config = _test_config(population_size=20, lifespan_range=(15, 30))
    repo = Repository(":memory:")
    pop = Population(config, repo, rng=np.random.default_rng(2024))
    pop.initialize()

    for _ in range(50):
        pop.run_tick()
        assert len(pop.alive) <= config.population_size

    all_agents = repo.list_agents()
    dead_agents = [a for a in all_agents if a["status"] == "dead"]
    born_agents = [a for a in all_agents if a["generation"] > 0]

    assert len(all_agents) > config.population_size  # births occurred
    assert len(dead_agents) > 0  # deaths occurred
    assert len(born_agents) > 0  # at least one child was actually born
