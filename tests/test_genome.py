import numpy as np

from evoconnect4.agent.genome import Genome, crossover, decode, encode, mutate, random_genome
from evoconnect4.agent.network import weight_count
from evoconnect4.config import load_config

CONFIG = load_config()
RNG = np.random.default_rng(42)


def test_genome_constructs_and_reads_back_fields():
    weights = np.zeros(10)
    genome = Genome(weights=weights, hidden_layer_sizes=[24], lifespan=100, mutation_rate=0.1, crossover_rate=0.5)
    assert np.array_equal(genome.weights, weights)
    assert genome.hidden_layer_sizes == [24]
    assert genome.lifespan == 100
    assert genome.mutation_rate == 0.1
    assert genome.crossover_rate == 0.5


def test_random_genome_has_correct_weight_count():
    genome = random_genome(CONFIG, rng=RNG)
    input_size = CONFIG.board_columns * CONFIG.board_rows
    hidden_size = CONFIG.hidden_layer_sizes[0]
    output_size = CONFIG.board_columns
    assert genome.weights.shape == (weight_count(input_size, hidden_size, output_size),)


def test_random_genome_trait_genes_within_configured_bounds():
    lifespan_min, lifespan_max = CONFIG.lifespan_range
    mutation_min, mutation_max = CONFIG.mutation_rate_range
    crossover_min, crossover_max = CONFIG.crossover_rate_range

    for _ in range(50):
        genome = random_genome(CONFIG, rng=RNG)
        assert lifespan_min <= genome.lifespan <= lifespan_max
        assert mutation_min <= genome.mutation_rate <= mutation_max
        assert crossover_min <= genome.crossover_rate <= crossover_max


def test_encode_decode_round_trips():
    original = random_genome(CONFIG, rng=RNG)
    restored = decode(encode(original))
    assert np.array_equal(restored.weights, original.weights)
    assert restored.hidden_layer_sizes == original.hidden_layer_sizes
    assert restored.lifespan == original.lifespan
    assert restored.mutation_rate == original.mutation_rate
    assert restored.crossover_rate == original.crossover_rate


def test_mutate_does_not_modify_the_parent():
    parent = random_genome(CONFIG, rng=RNG)
    parent_weights_copy = parent.weights.copy()

    child = mutate(parent, CONFIG, rng=RNG)

    assert np.array_equal(parent.weights, parent_weights_copy)
    assert child is not parent
    assert not np.array_equal(child.weights, parent.weights)


def test_mutate_keeps_trait_genes_within_configured_bounds():
    lifespan_min, lifespan_max = CONFIG.lifespan_range
    mutation_min, mutation_max = CONFIG.mutation_rate_range
    crossover_min, crossover_max = CONFIG.crossover_rate_range

    genome = random_genome(CONFIG, rng=RNG)
    for _ in range(50):
        genome = mutate(genome, CONFIG, rng=RNG)
        assert lifespan_min <= genome.lifespan <= lifespan_max
        assert mutation_min <= genome.mutation_rate <= mutation_max
        assert crossover_min <= genome.crossover_rate <= crossover_max


def test_crossover_child_weights_come_from_one_parent_or_the_other():
    parent_a = random_genome(CONFIG, rng=RNG)
    parent_b = random_genome(CONFIG, rng=RNG)

    child = crossover(parent_a, parent_b, rng=RNG)

    for w, a, b in zip(child.weights, parent_a.weights, parent_b.weights):
        assert w == a or w == b


def test_crossover_trait_genes_are_the_average_of_both_parents():
    parent_a = random_genome(CONFIG, rng=RNG)
    parent_b = random_genome(CONFIG, rng=RNG)

    child = crossover(parent_a, parent_b, rng=RNG)

    assert child.lifespan == round((parent_a.lifespan + parent_b.lifespan) / 2)
    assert np.isclose(child.mutation_rate, (parent_a.mutation_rate + parent_b.mutation_rate) / 2)
    assert np.isclose(child.crossover_rate, (parent_a.crossover_rate + parent_b.crossover_rate) / 2)
