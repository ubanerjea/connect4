import dataclasses
import shutil

import pytest

from evoconnect4.config import load_config
from evoconnect4.run_simulation import (
    CorruptDatabaseError,
    FrozenConfigMismatch,
    _default_db_path,
    _parse_args,
    run,
)
from evoconnect4.storage.repository import Repository

BASE_CONFIG = load_config()


def _test_config(**overrides):
    return dataclasses.replace(BASE_CONFIG, **overrides)


# -- 1.1 CLI args -------------------------------------------------------------


def test_parse_args_defaults():
    args = _parse_args([])
    assert args.ticks == 500
    assert args.seed is None
    assert args.db is None


def test_parse_args_ticks_override():
    args = _parse_args(["--ticks", "50"])
    assert args.ticks == 50


def test_default_db_path_is_timestamped_under_data_dir():
    path = _default_db_path()
    assert path.startswith("data/evoconnect4_")
    assert path.endswith(".db")


# -- 1.2 Fresh start ------------------------------------------------------------


def test_fresh_run_populates_all_three_new_tables(tmp_path):
    db_path = str(tmp_path / "fresh.db")
    config = _test_config(population_size=8)

    run(ticks=3, seed=7, db_path=db_path, config=config)

    repo = Repository(db_path)
    sim_config = repo.get_simulation_config()
    state = repo.get_simulation_state()
    history = repo.get_effective_config_at_tick(0)

    assert sim_config is not None
    assert isinstance(sim_config["simulation_id"], str) and len(sim_config["simulation_id"]) > 0
    assert sim_config["board_columns"] == config.board_columns
    assert state is not None
    assert state["current_tick"] == 3
    assert history is not None
    assert history["random_seed"] == 7


def test_fresh_run_falls_back_to_configured_seed_when_no_override(tmp_path):
    db_path = str(tmp_path / "fresh_default_seed.db")
    config = _test_config(population_size=4)

    run(ticks=1, seed=None, db_path=db_path, config=config)

    repo = Repository(db_path)
    assert repo.get_effective_config_at_tick(0)["random_seed"] == config.random_seed


# -- 1.3 Fresh vs resume decision ----------------------------------------------


def test_second_invocation_resumes_instead_of_recreating(tmp_path):
    db_path = str(tmp_path / "resume.db")
    config = _test_config(population_size=6)

    run(ticks=3, seed=1, db_path=db_path, config=config)
    repo = Repository(db_path)
    simulation_id_before = repo.get_simulation_config()["simulation_id"]

    run(ticks=2, seed=None, db_path=db_path, config=config)
    repo = Repository(db_path)

    assert repo.get_simulation_config()["simulation_id"] == simulation_id_before
    assert repo.get_simulation_state()["current_tick"] == 5


def test_corrupt_database_missing_simulation_config_raises(tmp_path):
    db_path = str(tmp_path / "corrupt.db")
    config = _test_config(population_size=4)

    # Create a database with an alive agent but no simulation_config record,
    # bypassing run()'s fresh-start path entirely.
    repo = Repository(db_path)
    repo.insert_agent(
        parent1_id=None, parent2_id=None, generation=0, birth_tick=0, status="alive",
        nn_weights=[0.1], nn_architecture=[24], lifespan=100, mutation_rate=0.1, crossover_rate=0.5,
    )
    repo.commit()
    repo.close()

    with pytest.raises(CorruptDatabaseError):
        run(ticks=1, seed=None, db_path=db_path, config=config)


# -- 1.4 Seed / RNG continuity --------------------------------------------------


def test_resume_without_seed_continues_bit_for_bit_identically(tmp_path):
    config = _test_config(population_size=10)

    continuous_db = str(tmp_path / "continuous.db")
    run(ticks=8, seed=123, db_path=continuous_db, config=config)

    split_db = str(tmp_path / "split.db")
    run(ticks=5, seed=123, db_path=split_db, config=config)
    run(ticks=3, seed=None, db_path=split_db, config=config)

    def _agent_fingerprint(db_path):
        repo = Repository(db_path)
        agents = repo.list_agents()
        return sorted(
            (a["agent_id"], a["status"], a["parent1_id"], a["parent2_id"], a["fitness"], tuple(a["nn_weights"]))
            for a in agents
        )

    assert _agent_fingerprint(continuous_db) == _agent_fingerprint(split_db)

    continuous_state = Repository(continuous_db).get_simulation_state()
    split_state = Repository(split_db).get_simulation_state()
    assert continuous_state["rng_state"] == split_state["rng_state"]
    assert continuous_state["current_tick"] == split_state["current_tick"] == 8


def test_resume_with_seed_override_diverges_from_unbroken_continuation(tmp_path):
    config = _test_config(population_size=10)

    base_db = str(tmp_path / "base.db")
    run(ticks=5, seed=123, db_path=base_db, config=config)

    unbroken_db = str(tmp_path / "unbroken.db")
    diverged_db = str(tmp_path / "diverged.db")
    shutil.copyfile(base_db, unbroken_db)
    shutil.copyfile(base_db, diverged_db)

    run(ticks=3, seed=None, db_path=unbroken_db, config=config)
    run(ticks=3, seed=999, db_path=diverged_db, config=config)

    unbroken_state = Repository(unbroken_db).get_simulation_state()
    diverged_state = Repository(diverged_db).get_simulation_state()
    assert unbroken_state["rng_state"] != diverged_state["rng_state"]

    history = Repository(diverged_db).get_effective_config_at_tick(5)
    assert history["random_seed"] == 999


# -- 1.5 Resume-time frozen-config validation -----------------------------------


def test_resume_refuses_on_frozen_field_mismatch_and_leaves_db_untouched(tmp_path):
    db_path = str(tmp_path / "frozen_mismatch.db")
    config = _test_config(population_size=4)

    run(ticks=2, seed=1, db_path=db_path, config=config)
    state_before = Repository(db_path).get_simulation_state()

    mismatched_config = _test_config(population_size=4, board_columns=6)
    with pytest.raises(FrozenConfigMismatch) as exc_info:
        run(ticks=2, seed=None, db_path=db_path, config=mismatched_config)

    assert "board_columns" in str(exc_info.value)
    state_after = Repository(db_path).get_simulation_state()
    assert state_after == state_before


# -- 1.6 Mutable config history on resume ---------------------------------------


def test_resume_appends_history_row_only_when_mutable_field_changes(tmp_path):
    db_path = str(tmp_path / "history.db")
    config = _test_config(population_size=4, tournament_size=5)

    run(ticks=2, seed=1, db_path=db_path, config=config)

    changed_config = _test_config(population_size=4, tournament_size=8)
    run(ticks=2, seed=None, db_path=db_path, config=changed_config)

    repo = Repository(db_path)
    assert repo.get_effective_config_at_tick(0)["tournament_size"] == 5
    assert repo.get_effective_config_at_tick(4)["tournament_size"] == 8


def test_resume_appends_no_history_row_when_nothing_changed(tmp_path):
    db_path = str(tmp_path / "no_history_change.db")
    config = _test_config(population_size=4)

    run(ticks=2, seed=1, db_path=db_path, config=config)
    run(ticks=2, seed=None, db_path=db_path, config=config)

    repo = Repository(db_path)
    rows = repo.conn.execute("SELECT COUNT(*) FROM simulation_config_history").fetchone()[0]
    assert rows == 1


# -- 1.7 Full-run verification (Phase 5 DoD) -------------------------------------


def test_several_hundred_tick_run_completes_without_error(tmp_path):
    db_path = str(tmp_path / "full_run.db")
    config = _test_config(population_size=20, lifespan_range=(15, 30))

    run(ticks=300, seed=2024, db_path=db_path, config=config)

    repo = Repository(db_path)
    state = repo.get_simulation_state()
    assert state["current_tick"] == 300
    assert len(repo.list_agents()) > config.population_size
