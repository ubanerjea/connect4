## Why

EvoConnect4 has a game engine (Phase 1) and evolvable agents (Phase 2), but nowhere to persist them. Phase 4's evolution loop needs somewhere to record agents, games, and population state as it runs; Phase 3 of the plan's roadmap (§11) builds that persistence layer now, ahead of the loop that will drive it, so Phase 4 can focus purely on evolutionary mechanics against a storage layer that already works.

## What Changes

- Add a SQLite schema (`src/evoconnect4/storage/schema.py`) matching plan §6 exactly: `agents`, `games`, `population_snapshots`, and `benchmark_results` tables, plus the indices §6 calls out (`agents.status`, `agents.parent1_id`/`parent2_id`, `games.tick`, `games.player1_agent_id`/`player2_agent_id`). Uses plain `sqlite3` (stdlib) — no new dependency. `benchmark_results` is defined now (it's part of the same schema) but has no reader/writer built until Phase 6 actually produces benchmark data.
- Add a `Repository` (`src/evoconnect4/storage/repository.py`) wrapping a SQLite connection, providing full CRUD for `agents` and `games` (insert, get by id, list/filter, update — e.g. an agent's stats or status as games are played, per §4.2's tick loop that Phase 4 will drive) and insert/read for `population_snapshots`. This goes beyond §11's literal Phase 3 DoD ("insert a fake agent + game, read both back correctly") to match §7's framing of `repository.py` as owning "all reads/writes to SQLite" — none of the extra CRUD needs anything beyond the schema this same change builds, unlike Phase 6's benchmark-scheduling machinery which genuinely needs a live population.
- A genome's existing `encode()`/`decode()` (Phase 2) round-trips through `agents.nn_weights`/`nn_architecture` via `json.dumps`/`json.loads` — the dict form Phase 2 built specifically anticipating this DB storage now gets its first real consumer.
- Database path is a constructor parameter to `Repository` (default `data/evoconnect4.db`), not a new `config.yaml` tunable — it isn't one of §10's listed parameters, and tests use `:memory:` directly.

## Capabilities

### New Capabilities
- `database-storage`: Durable SQLite storage for agents, games, and population snapshots — schema creation, and CRUD/insert-and-read operations satisfying plan §6's data model.

### Modified Capabilities

None.

## Impact

- New files: `src/evoconnect4/storage/schema.py`, `src/evoconnect4/storage/repository.py`, `tests/test_schema.py`, `tests/test_repository.py`.
- New directory created at runtime: `data/` (already `.gitignore`d from Phase 0).
- No new dependencies — `sqlite3` is stdlib.
- No changes to `src/evoconnect4/game/` or `src/evoconnect4/agent/` — `Repository` consumes `Genome.encode()`'s existing dict output read-only; nothing in Phase 1/2 changes shape.
