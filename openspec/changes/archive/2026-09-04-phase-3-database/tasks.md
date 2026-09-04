## 1. Schema

- [x] 1.1 Implement `create_schema(conn)` creating the `agents`, `games`, `population_snapshots`, and `benchmark_results` tables matching plan §6's field lists exactly, plus the indices §6 names (`agents.status`, `agents.parent1_id`/`parent2_id`, `games.tick`, `games.player1_agent_id`/`player2_agent_id`), and verify a unit test asserts all 4 tables and each index exist after running it against a fresh in-memory database

## 2. Repository Core

- [x] 2.1 Implement `Repository(db_path)` opening a `sqlite3` connection, enabling `PRAGMA foreign_keys = ON`, calling `create_schema`, and supporting use as a context manager (closes the connection on exit), and verify a unit test opens a `Repository` against `:memory:` and confirms the schema exists

## 3. Agent CRUD

- [x] 3.1 Implement `insert_agent(...) -> agent_id`, serializing a genome's `encode()` output into `nn_weights`/`nn_architecture` via `json.dumps`, and verify a round-trip unit test: insert then `get_agent` returns identical fields, with the genome data decoding back to the original weights and architecture
- [x] 3.2 Implement `get_agent(agent_id) -> record | None`, and verify a unit test confirms it returns `None` for a nonexistent id
- [x] 3.3 Implement `update_agent_stats(agent_id, games_played, wins, losses, draws, fitness, games_since_last_reproduction)`, and verify a unit test updates an inserted agent's stats and confirms a subsequent read reflects the new values, not the original ones
- [x] 3.4 Implement `mark_agent_dead(agent_id, death_tick, death_cause)`, and verify a unit test marks an inserted agent dead and confirms a subsequent read shows `status='dead'` with the given tick and cause
- [x] 3.5 Implement `list_agents(status=...)` filtering by status, and verify a unit test with a mix of alive and dead agents confirms listing by alive status returns only the alive ones

## 4. Game CRUD

- [x] 4.1 Implement `insert_game(...) -> game_id`, serializing `move_history` via `json.dumps`, and verify a round-trip unit test: insert then `get_game` returns identical fields, including the decoded move history
- [x] 4.2 Implement `get_game(game_id) -> record | None`, and verify a unit test confirms it returns `None` for a nonexistent id
- [x] 4.3 Implement `list_games(tick=...)` filtering by tick, and verify a unit test with games recorded across multiple ticks confirms listing by one tick returns only that tick's games

## 5. Population Snapshot

- [x] 5.1 Implement `insert_snapshot(...) -> snapshot_id`, and verify a round-trip unit test: insert then read returns identical fields
- [x] 5.2 Implement `get_latest_snapshot() -> record | None`, and verify a unit test with snapshots recorded at multiple ticks confirms it returns the one with the highest tick

## 6. Full Suite Verification

- [x] 6.1 Verify `uv run pytest` passes across `tests/test_schema.py`, `tests/test_repository.py`, and all existing Phase 0-2 tests with zero failures
- [x] 6.2 Verify plan §11's Phase 3 roadmap bar is met — inserting a fake agent and a fake game and reading both back correctly — is present and passing in the suite from 6.1
