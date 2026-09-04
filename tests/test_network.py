import numpy as np

from evoconnect4.agent.network import Network, weight_count


def test_network_reshapes_flat_vector_into_correct_layer_shapes():
    weights = np.zeros(weight_count(input_size=3, hidden_size=4, output_size=2))
    net = Network(weights, input_size=3, hidden_size=4, output_size=2)
    assert net.w1.shape == (3, 4)
    assert net.b1.shape == (4,)
    assert net.w2.shape == (4, 2)
    assert net.b2.shape == (2,)


def test_forward_pass_matches_hand_computed_value():
    # W1 = identity(2), b1 = 0, W2 = [[1], [1]], b2 = 0
    # forward(x) = tanh(x) . [1, 1] = tanh(x0) + tanh(x1)
    weights = np.array([1, 0, 0, 1, 0, 0, 1, 1, 0], dtype=float)
    net = Network(weights, input_size=2, hidden_size=2, output_size=1)

    x = np.array([1.0, 2.0])
    result = net.forward(x)

    expected = np.tanh(1.0) + np.tanh(2.0)
    assert result.shape == (1,)
    assert np.isclose(result[0], expected)


def test_flatten_round_trips_a_random_weight_vector():
    rng = np.random.default_rng(0)
    original = rng.normal(size=weight_count(input_size=5, hidden_size=6, output_size=3))
    net = Network(original, input_size=5, hidden_size=6, output_size=3)
    assert np.array_equal(net.flatten(), original)
