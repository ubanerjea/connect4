from evoconnect4.config import Config, load_config


def test_load_config_returns_config_instance():
    config = load_config()
    assert isinstance(config, Config)


def test_load_config_reads_expected_defaults():
    config = load_config()
    assert config.population_size == 100
    assert config.board_columns == 7
    assert config.board_rows == 6
    assert config.random_seed == 42


def test_load_config_field_types():
    config = load_config()
    assert isinstance(config.population_size, int)
    assert isinstance(config.weight_init_std, float)
    assert isinstance(config.hidden_layer_sizes, list)
    assert isinstance(config.lifespan_range, tuple)
    assert isinstance(config.mutation_rate_range, tuple)
