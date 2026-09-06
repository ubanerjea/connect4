## Context

`benchmark_results` has existed in the schema since Phase 3 but has no reader/writer. `game/bots.py`'s `random_mover`/`heuristic_bot` exist since Phase 1 but are only used by tests — nothing in the tick loop calls them. `game/match.py`'s `play_match(chooser_a, chooser_b, first_mover)` already treats "chooser" as any `Board -> int` callable and always maps `chooser_a` to board position `1`, `chooser_b` to board position `-1`, independent of `first_mover` (confirmed by reading `_play_pair`'s existing use: `agent_a` is always DB `player1`, regardless of who moves first that game). `games.player1_agent_id`/`player2_agent_id` are currently both `NOT NULL REFERENCES agents(agent_id)` — a bot or human has no `agents` row. `random_mover`/`heuristic_bot` currently call Python's global `random.choice`, not the project's single injected `np.random.Generator` (`population.rng`) that everything else — genome mutation, culling, pairing, RNG-state persistence (Phase 5) — is deliberately routed through for reproducibility.

See proposal.md for motivation; see the two delta specs for full behavioral requirements.

## Goals / Non-Goals

**Goals:**
- A benchmark step that fires on schedule, evaluates the current-best agent against both fixed bots, and records results durably — the literal Phase 6 roadmap item.
- Keep benchmark ticks exactly as reproducible as every other tick under Phase 5's resume/seed machinery.
- Store benchmark games with full move-history detail, not just an aggregate, using the same `games` table evolution games already use — and leave that table correctly shaped for Phase 8's human-play games too.

**Non-Goals:**
- Any change to what counts toward reproductive fitness — benchmark games are recorded but never touch an agent's `wins`/`losses`/`draws`/`games_played`/`fitness`. Letting them (or human games) count later is a noted, deliberately deferred extension (plan §13), not this phase.
- Moving fitness computation from incrementally-maintained counters to a live query over `games` — considered and rejected; see Risks/Trade-offs.
- Phase 8's human-play CLI itself.
- A database-level `CHECK` constraint for the new `games` invariant — enforced in `Repository.insert_game` instead, by explicit preference against complex multi-column `CHECK` expressions.

## Decisions

### Benchmark step placement: after death/culling, before the snapshot write
`Population._run_benchmark()` is called from `run_tick()` in that exact position, matching plan §4.2's own pseudocode order. This means "current best agent" is selected from `self.alive` *after* that tick's reproduction, death, and culling have already run — an agent that gets culled this same tick is never benchmarked.

### Bots gain an optional `rng` parameter, not a required one
`random_mover(board, rng=None)` / `heuristic_bot(board, rng=None)` fall back to the existing stdlib `random.choice` calls when `rng` is omitted, so the three pre-existing bot tests (which call them with a single `board` argument) keep passing unchanged. The benchmark step binds `population.rng` before passing a bot in as a `play_match` chooser — via a small closure or `functools.partial`, so `match.py`'s `Chooser = Callable[[Board], int]` contract needs no change at all. `rng.choice(...)` results are cast to plain `int` (numpy scalar types are otherwise returned). Without this, any run whose `--ticks` range crosses a `benchmark_every_n_ticks` boundary would silently break Phase 5's bit-for-bit resume guarantee.

### `games` invariant: agent always in `player1_agent_id`, validated in `Repository.insert_game`
For any `game_type` other than `'evolution'`, the agent occupies `player1_agent_id` (never `player2_agent_id`), `player2_agent_id` is `NULL`, and `opponent_label` is required. This is deliberate, not arbitrary: it keeps `result` self-explanatory (`'player1_win'` always means "the agent won" for a benchmark/human row) and makes the evolution/non-evolution distinction a single-column check (`player2_agent_id IS NOT NULL`). Validation lives in `Repository.insert_game` — a single choke point — rather than a SQL `CHECK` constraint: neither `game_type` nor `result` has any DB-level enum enforcement today either (both are plain `TEXT NOT NULL`), and app-level keeps the logic readable rather than an increasingly complex multi-column `CHECK` expression, per explicit preference.

### `opponent_label` vocabulary must match `benchmark_results.opponent_type` for benchmark rows
`'random'` / `'heuristic'` — not `'random_mover'`/`'heuristic_bot'` or any other naming scheme — so `games` and `benchmark_results` stay joinable without a translation layer. For `human_vs_agent` rows (Phase 8, not this phase), `opponent_label` is genuinely free text.

### `Repository` CRUD stays minimal: one filter parameter, matching existing convention
`list_benchmark_results(*, tick: int | None = None)` mirrors the one-optional-filter pattern already used by `list_games(tick=...)` and `list_agents(status=...)`. No `agent_id`/`opponent_type` filter parameters — benchmark result volume is tiny (roughly two rows per benchmark tick), and plan §9's chart (win-rate vs. random and vs. heuristic, over time) needs the whole trend anyway; grouping by `opponent_type` at chart-build time in Python/pandas is simpler than adding repository-layer filters for a case that doesn't need them.

## Risks / Trade-offs

- **No DB-level enforcement of the `games` invariant** → a direct write to `games` that bypasses `Repository.insert_game` could violate it undetected. Accepted, per explicit preference against complex `CHECK` constraints, and consistent with `game_type`/`result` already having no DB-level enum enforcement.
- **Relaxing `games.player1_agent_id`/`player2_agent_id` to nullable is a breaking schema change to an already-archived table** → acceptable at this project's stage: no `data/*.db` file exists yet in the repository, so there is no real data to migrate (same reasoning as Phase 5's `agents.parent_avg_fitness` addition).
- **Query-based fitness was considered and rejected** for this phase's design: fitness is recomputed for every alive agent every tick, so a query-based approach would replace cheap O(1) in-memory arithmetic with `population_size` SQL queries per tick, growing more expensive as each agent's game history grows; it would also need to handle reading not-yet-committed game rows within the same tick (commits are deliberately batched once per tick, per plan §6), and would undermine Phase 5's O(1)-per-agent `Population.load()` resume path. Fitness stays exactly as it is today — untouched by this phase.
