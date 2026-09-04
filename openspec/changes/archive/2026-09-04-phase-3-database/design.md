## Context

This is the project's first persistence layer — nothing in Phase 0-2 touches a database. Plan §6 already fully specifies the schema (four tables, field lists, indices, the batch-commit note); this change implements that schema and the CRUD Phase 4 will need, without yet having a tick loop to exercise it against real simulation data. See proposal.md - Why.

## Goals / Non-Goals

**Goals:**
- A schema and CRUD surface Phase 4 can consume unchanged when it builds the tick loop.
- Round-trip fidelity for every field plan §6 specifies, including genome data via Phase 2's existing `encode()`/`decode()`.

**Non-Goals:**
- `benchmark_results` CRUD — the table is created (it's part of the same schema), but no reader/writer is built until Phase 6 actually produces benchmark data.
- Deciding *when* to commit during a tick (§6's batching note) — that's Phase 4's tick-loop concern. This change only needs to not force a commit per insert, so batching is possible later.
- Schema migrations/versioning — the database is regenerated fresh per run; no need to evolve an existing one in place.

## Decisions

**Plain `sqlite3` (stdlib), not SQLAlchemy.** Decided directly with the user: no new dependency, consistent with the project's minimal-dependency approach so far (only `numpy`/`pyyaml` added since Phase 0). More boilerplate per CRUD operation than an ORM, but full control and nothing new to learn.

**`Repository` is a class wrapping a `sqlite3.Connection`, not a module of functions taking a connection each call.** Matches §7's framing of `repository.py` as owning "all reads/writes to SQLite," and avoids threading a `conn` parameter through every call site in Phase 4's future tick loop. `Repository(db_path)` opens the connection (or accepts `:memory:` for tests) and creates the schema if needed; supports use as a context manager for clean close.

**Insert methods do not auto-commit; `Repository.commit()` is explicit.** Directly serves §6's "commit games in a batch at the end of each tick rather than one commit per game" note — Phase 4's tick loop can insert many rows and commit once. Phase 3's own tests call `.commit()` for clarity, though reads on the same connection see uncommitted writes regardless (SQLite's own transaction visibility), so it isn't strictly required within a single connection.

**JSON fields (`nn_weights`, `nn_architecture`, `move_history`) are stored as `TEXT` via `json.dumps`/`json.loads`, not `BLOB`.** §6 says "JSON/blob" — TEXT keeps the stored data human-inspectable (`sqlite3` CLI, DB browsers) with no encoding complexity `BLOB` would add for what's already a JSON string. `Genome.encode()`'s dict output (Phase 2, built anticipating exactly this) is what gets `json.dumps`-ed into `nn_weights`/`nn_architecture`; `Genome.decode()` is what reconstructs it on read.

**Foreign keys are enforced (`PRAGMA foreign_keys = ON`).** §6 defines real FK relationships (`agents.parent1_id`/`parent2_id`, `games.player1_agent_id`/`player2_agent_id`, `population_snapshots.best_agent_id`, `benchmark_results.agent_id`, all → `agents`). SQLite doesn't enforce these by default per connection; enabling it catches referential-integrity bugs early (e.g. inserting a game against a nonexistent agent) rather than silently allowing them.

**Primary keys use `INTEGER PRIMARY KEY` (SQLite's rowid alias) and rely on `cursor.lastrowid`** for the new id after insert — the standard, idiomatic `sqlite3` pattern; no need for a separate autoincrement scheme.

**`get_agent`/`get_game` return `None` when not found, rather than raising.** A missing id is an expected, common case (not an error), consistent with dict-like lookup semantics elsewhere in Python.

**Agent updates are two focused methods, not one generic kwargs updater:** `update_agent_stats(agent_id, games_played, wins, losses, draws, fitness, games_since_last_reproduction)` for the per-game bookkeeping §4.2's tick loop will do repeatedly, and `mark_agent_dead(agent_id, death_tick, death_cause)` for the one-time death transition (§4.4). Matches how Phase 4 will actually call these — clearer intent than a single flexible updater, and avoids partial-update ambiguity (which fields were and weren't touched).

**Database path is a `Repository` constructor parameter (default `data/evoconnect4.db`), not a `config.yaml` key.** It isn't one of §10's listed tunables, and tests pass `:memory:` directly rather than touching config.

## Risks / Trade-offs

- [Explicit-commit design means a caller who forgets to commit loses data on close] → Accepted; Phase 4's tick loop is the one real caller beyond tests, and its own design (§6's batching note) already requires an explicit per-tick commit point.
- [Two narrow agent-update methods instead of one generic updater means adding a new mutable field later requires a new method or signature change] → Accepted; the two methods map directly to the two ways plan §4 actually mutates an agent (per-game stats, one-time death), and explicit signatures catch mistakes a kwargs dict wouldn't.
- [`benchmark_results` table exists with no code reading/writing it until Phase 6] → Accepted; it's a static schema definition with no behavior, cheap to carry forward, and matches §6 being already fully specified.
