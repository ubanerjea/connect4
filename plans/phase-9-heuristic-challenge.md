# Phase 9 — Heuristic Challenge: Introducing External Selection Pressure

*Every agent plays a fixed number of games against the heuristic bot each tick, with results feeding into a two-track fitness formula that weights heuristic performance explicitly and independently of peer-game performance — breaking the closed-pool Red Queen trap. See `evoconnect4_project_plan.md` §11.*

This document is a self-contained brief for entering the OpenSpec propose/apply cycle. It assumes Phases 0–8 are already built and archived — in particular Phase 1's `game/bots.py` (`heuristic_bot`) and `game/match.py` (`play_match`), Phase 4/4b's tick loop and `_persist_stats` machinery, Phase 5's RNG-continuity machinery, Phase 6's nullable-agent-id `games` schema and `insert_game` invariant, and Phase 8's `game_type` vocabulary.

## Why

The benchmark data from a 5500-tick run diagnosed the problem precisely: heuristic win rate was 0.000 at 548 of 550 benchmark points, and two isolated non-zero readings (max 0.300) were noise from the 20-game sample. Meanwhile a human can trivially beat the best alive agent by stacking four discs in the same column — the simplest possible threat — because the agents never learned to block. Internal population fitness (avg ≈ 0.50 throughout the entire run) was no signal at all: it's zero-sum within the pool, so the average mathematically anchors at 0.5 regardless of how weak the pool actually is.

This is the Red Queen trap the project plan explicitly anticipated (§5, §14): agents are selected for beating their current pool-mates, not for playing well. Nothing in the current loop has ever punished an agent for failing to block a three-in-a-row.

The fix has two interlocking parts:

1. **Put the heuristic inside the fitness loop.** Every agent plays heuristic games each tick, with results counting toward fitness — creating selection pressure toward blocking from tick 1 rather than waiting for agents to stumble into wins by chance.

2. **Give losses a gradient.** A binary win/loss signal against a bot that wins 100% of games early in the run provides no differential signal — every agent loses, every agent gets the same fitness contribution. Survival credit (partial fitness for longer losses) creates a gradient that exists from the very first tick: an agent that blocks a vertical threat and extends a game to 28 moves gets meaningfully more credit than one that lets the heuristic win in 8.

## Scope

**In scope:**

1. Three new config parameters: `heuristic_games_per_agent_per_tick`, `heuristic_survival_alpha` (α), and `heuristic_fitness_weight` (β).
2. A new `Population._run_heuristic_challenges()` step in `run_tick()`, called **after peer games and before `_recompute_fitness()`**, so heuristic results feed into that tick's fitness recalculation.
3. A two-track fitness formula (Option C) replacing the current unified formula. Peer games and heuristic games each maintain separate counter sets; overall fitness is a β-weighted blend of the two resulting fitness scores.
4. Survival credit on heuristic losses only: partial fitness proportional to game length, scaled by α. Wins and draws on the heuristic track are scored normally (1.0 and 0.5 respectively); the credit applies only when the heuristic wins, to give early differential signal before agents can win or draw.
5. Seven new columns on the `agents` table: `peer_wins`, `peer_draws`, `peer_games_played`, `heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`. The existing `wins`, `losses`, `draws`, `games_played` columns are retained as total-across-all-games counters for analytics and lifespan tracking; `games_played` specifically continues to drive the lifespan countdown.
6. Heuristic challenge games logged to the `games` table with `game_type='evolution_heuristic'`.
7. `Repository.insert_game` invariant updated to admit `game_type='evolution_heuristic'`.
8. `run_simulation.py`'s `MUTABLE_FIELDS` updated with the three new params.
9. `config.py`/`config.yaml` updated.

**Out of scope:**

- Any change to the benchmark system (Phase 6) — benchmarks remain excluded from agent stats and serve as the independent external validity check. Heuristic challenge games and benchmark games play different roles: the former are selection pressure; the latter are measurement.
- Analytics chart changes — the existing `benchmark_win_rate_over_time.png` is still the primary external validity signal. Heuristic challenge game win rates and survival credit trends are queryable from the `games` and `agents` tables.
- Any change to `population_snapshots` — snapshot columns are untouched.

## Design

### The core mechanic

Each tick, after peer pairing games complete, **every alive agent** plays exactly `heuristic_games_per_agent_per_tick` games against the heuristic bot, alternating first mover. This is deterministic — there is no random selection of which agents are challenged. The heuristic is always `chooser_b` in `play_match`; the agent is always `chooser_a`, so `result.winner == 1` always means "the agent won," independent of who moved first.

Results update the agent's heuristic-track counters (`heuristic_wins`, `heuristic_draws`, `heuristic_games_played`, `heuristic_survival_credit`) and the unified totals (`wins`, `losses`, `draws`, `games_played`, `games_since_last_reproduction`). Then `_recompute_fitness()` computes the two-track fitness from the split counters.

```
_run_heuristic_challenges() pseudocode:

IF heuristic_games_per_agent_per_tick <= 0: return
IF self.alive is empty: return

bound_heuristic = functools.partial(heuristic_bot, rng=self.rng)

FOR agent IN self.alive:
    FOR i IN range(heuristic_games_per_agent_per_tick):
        first_mover = 1 if i % 2 == 0 else -1
        result = play_match(agent.choose_move, bound_heuristic, first_mover=first_mover)

        IF result.winner == 1:
            db_result = "player1_win"
            agent.heuristic_wins += 1
            agent.wins += 1
        ELIF result.winner == -1:
            db_result = "player2_win"
            agent.heuristic_survival_credit += alpha * result.num_moves / (board_columns * board_rows)
            agent.losses += 1
        ELSE:
            db_result = "draw"
            agent.heuristic_draws += 1
            agent.draws += 1

        agent.heuristic_games_played += 1
        agent.games_played += 1
        agent.games_since_last_reproduction += 1

        repo.insert_game(
            tick=self.tick,
            player1_agent_id=agent.agent_id,
            player2_agent_id=None,
            result=db_result,
            num_moves=result.num_moves,
            move_history=result.move_history,
            game_type="evolution_heuristic",
            opponent_label="heuristic",
        )
        self._persist_stats(agent)
```

*(Pseudocode — same convention as plan §4.2. `board_columns * board_rows` = 42 for the standard 7×6 board, accessed through `self.config`.)*

Peer games update the peer-track counters and unified totals in the same symmetric way, inside `_record_game`. No changes to `_play_pair` or `_pair_alive`.

### Two-track fitness formula (Option C)

```
peer_fitness      = (peer_wins + 0.5 * peer_draws) / peer_games_played
                    if peer_games_played > 0 else 0.0

heuristic_fitness = (heuristic_wins + 0.5 * heuristic_draws + heuristic_survival_credit)
                    / heuristic_games_played
                    if heuristic_games_played > 0 else 0.0

overall_fitness   = (1 - beta) * peer_fitness + beta * heuristic_fitness
```

`_recompute_fitness()` replaces its current single-formula line with these three lines. The result is written to `agent.fitness` as before; downstream code (reproduction interval, culling priority) is unchanged.

With defaults (`heuristic_games_per_agent_per_tick=2`, `games_per_pair_per_tick=2`, β=0.7):

- Peer and heuristic games are 1:1 in volume per tick (2 peer, 2 heuristic).
- β=0.7 makes heuristic performance 70% of overall fitness despite equal game volume — an explicit statement that external competence matters more than peer rank.
- An agent losing all heuristic games in 15 moves: `heuristic_fitness ≈ 0.5 * 15/42 ≈ 0.18`; with β=0.7 and peer_fitness=0.5: `overall ≈ 0.3*0.5 + 0.7*0.18 ≈ 0.28`.
- An agent losing in 28 moves: `heuristic_fitness ≈ 0.33`; `overall ≈ 0.3*0.5 + 0.7*0.33 ≈ 0.38`.
- A 10-point fitness gap exists from day 1, before any agent wins a single heuristic game.

Setting `beta=0.5` with equal game volume is mathematically equivalent to the simpler Option B (unified counters, no separate tracks); values above 0.5 amplify heuristic importance per game beyond what the 1:1 volume would imply.

### Where in `run_tick()` this executes

```
run_tick():
    self.tick += 1
    peer games (_pair_alive / _play_pair)          ← unchanged; updates peer track + unified totals
    heuristic challenges (_run_heuristic_challenges) ← NEW; updates heuristic track + unified totals
    _recompute_fitness()                            ← two-track formula; same call site
    reproduction / death loop                       ← unchanged; uses overall_fitness
    _run_benchmark()                                ← unchanged
    _write_snapshot()                               ← unchanged
    repo.commit()                                   ← unchanged
```

Placing heuristic challenges before `_recompute_fitness()` means heuristic results inform the fitness signal that drives that same tick's reproduction and culling, not just the next tick's. This maximises the tightness of the selection loop.

### Compute cost

With deterministic challenges for all 100 agents at 2 games each: 200 heuristic games per tick alongside ~100 peer games. This is roughly **3× the games per tick** compared to the current codebase. Pure-Python forward passes are fast enough that this is acceptable at the scale in §10; if wall-clock time becomes a constraint, reduce `heuristic_games_per_agent_per_tick` to 1.

### `agents` table: new columns

Seven new columns added to the `agents` table in `schema.py`:

```sql
peer_wins               INTEGER NOT NULL DEFAULT 0,
peer_draws              INTEGER NOT NULL DEFAULT 0,
peer_games_played       INTEGER NOT NULL DEFAULT 0,
heuristic_wins          INTEGER NOT NULL DEFAULT 0,
heuristic_draws         INTEGER NOT NULL DEFAULT 0,
heuristic_games_played  INTEGER NOT NULL DEFAULT 0,
heuristic_survival_credit REAL NOT NULL DEFAULT 0.0
```

The existing `wins`, `losses`, `draws`, `games_played` columns are retained unchanged. They continue to be updated for all game types and continue to drive the lifespan countdown (`games_played >= lifespan`). No existing columns are removed or renamed.

`Repository.update_agent_stats`, `Repository.insert_agent`, `Repository.get_agent`, and `Repository.list_agents` are updated to include the new columns. `Population.load()` is updated to restore the new counters from storage.

### Config additions

| Parameter | Default | Description |
|---|---|---|
| `heuristic_games_per_agent_per_tick` | `2` | Games every alive agent plays against the heuristic each tick (first-mover alternates). Set to `0` to disable all heuristic challenges and restore Phase 8 behavior. |
| `heuristic_survival_alpha` | `0.5` | Scales survival credit on heuristic losses: `credit += alpha * moves_played / 42`. At 0.5, a full-board survival is worth as much as a draw (0.5). |
| `heuristic_fitness_weight` | `0.7` | β in the two-track formula — the weight given to `heuristic_fitness` in `overall_fitness`. At 0.5 with equal game volumes, equivalent to a unified formula; above 0.5 amplifies heuristic importance per game. |

All three go in `MUTABLE_FIELDS` in `run_simulation.py` — changing them on resume is fine; they affect the fitness signal going forward but don't touch the frozen architecture.

`heuristic_games_per_agent_per_tick=0` exactly reproduces current Phase 8 behavior: `_run_heuristic_challenges()` returns immediately, no games generated, no counters changed. The new agent columns exist in the schema with value 0; fitness degrades gracefully to `(1-beta)*peer_fitness + beta*0 = (1-beta)*peer_fitness`.

### `games` table and `insert_game` invariant

No DDL changes to `games` — the existing schema (Phase 6) already accommodates this pattern. `'evolution_heuristic'` joins the nullable-player2 group in the `insert_game` validation:

| `game_type` | `player1_agent_id` | `player2_agent_id` | `opponent_label` |
|---|---|---|---|
| `'evolution'` | NOT NULL | NOT NULL | NULL |
| `'benchmark'` | NOT NULL | NULL | NOT NULL |
| `'human_vs_agent'` | NOT NULL | NULL | NOT NULL |
| `'evolution_heuristic'` *(new)* | NOT NULL | NULL | `'heuristic'` |

### `run_simulation.py` MUTABLE_FIELDS

```python
MUTABLE_FIELDS = (
    ...
    "heuristic_games_per_agent_per_tick",  # new
    "heuristic_survival_alpha",            # new
    "heuristic_fitness_weight",            # new
)
```

## Files changed

| File | Change |
|---|---|
| `config.yaml` | Add `heuristic_games_per_agent_per_tick: 2`, `heuristic_survival_alpha: 0.5`, `heuristic_fitness_weight: 0.7` |
| `src/evoconnect4/config.py` | Add three new fields to `Config` dataclass; wire in `load_config()` |
| `src/evoconnect4/storage/schema.py` | Add seven new columns to `agents` DDL |
| `src/evoconnect4/storage/repository.py` | Update `insert_agent`, `update_agent_stats`, `get_agent`, `list_agents` for new columns; add `'evolution_heuristic'` to `insert_game` invariant |
| `src/evoconnect4/agent/agent.py` | Add seven new counter fields; update `_record_game`-equivalent stats accumulation for peer vs heuristic tracking |
| `src/evoconnect4/evolution/population.py` | Add `_run_heuristic_challenges()`; update `_record_game` to maintain peer-track counters; update `_recompute_fitness()` for two-track formula; update `load()` to restore new counters; call `_run_heuristic_challenges()` from `run_tick()` |
| `src/evoconnect4/run_simulation.py` | Add three new params to `MUTABLE_FIELDS` |

No changes to `game/bots.py` (already has the `rng` parameter from Phase 6), `game/match.py`, `interface/play_cli.py`, or `analytics/plots.py`.

## Definition of done

- `heuristic_games_per_agent_per_tick=0` produces identical behavior to the current Phase 8 codebase — no new games generated, no counters changed, RNG state identical at tick end, overall_fitness degrades cleanly to a peer-only signal.
- With `heuristic_games_per_agent_per_tick=2`: a 1000-tick run generates exactly 200k heuristic games (`evolution_heuristic` rows in `games`) alongside ~100k peer games. Every agent's `heuristic_games_played` equals `heuristic_games_per_agent_per_tick * ticks_alive`. No agent ever has `heuristic_games_played=0` after its first full tick.
- Two-track fitness formula computes correctly: unit test verifies `overall_fitness` for a known agent with controlled counter values against β=0.7 formula.
- Survival credit accrues only on heuristic losses, not wins or draws: unit test confirms `heuristic_survival_credit` increments after a simulated heuristic loss and is unchanged after a win or draw.
- `games_since_last_reproduction` increments for heuristic challenge games.
- `games_played` (unified) increments for both peer and heuristic games and continues to correctly gate the lifespan countdown.
- The `insert_game` invariant test from Phase 6 is extended: `game_type='evolution_heuristic'` with `player2_agent_id=None, opponent_label='heuristic'` is accepted; with `player2_agent_id` set, it is rejected.
- `Population.load()` correctly restores all seven new counters from the database, confirmed by a resume test where a run paused and resumed produces identical tick-by-tick fitness values.
- A Phase 5-style RNG resume test with heuristic challenges enabled confirms bit-for-bit continuity across a resume boundary.
- Full existing test suite passes.
- Over a multi-thousand-tick run with defaults, `benchmark_results` shows a measurably rising heuristic win rate and/or average game length in `evolution_heuristic` games trends upward — the empirical evidence that survival credit is creating selection pressure before agents can win.

## Risks and mitigations

**β too high, peer dynamics distorted.** At β=0.7, peer fitness is only 30% of overall fitness. If this causes agents to stop differentiating on peer game results, co-evolutionary dynamics weaken and the population could converge on "survive longer vs heuristic" without improving at peer play. Monitor average peer_fitness separately; if it collapses to noise, reduce β toward 0.5.

**Survival credit rewarding passive play.** An agent that maximises game length by random non-blocking could accrue survival credit without learning to block. Against the heuristic specifically, this is unlikely — the heuristic ends games decisively the moment a win is available, so the only reliable way to extend a game is to actually get in the heuristic's way. If pathological passive strategies emerge, reduce α to limit how much survival credit is worth relative to wins.

**Compute cost.** 3× games per tick compared to Phase 8. Acceptable at the default population size; reduce `heuristic_games_per_agent_per_tick` to 1 if wall-clock time becomes a constraint.

**Heuristic remains too strong after many ticks.** If agents reach a ceiling where they consistently extend games but never win, the next lever is introducing an intermediate opponent (e.g. a bot that only blocks, never plays for a win) on a curriculum schedule. The `heuristic_games_per_agent_per_tick=0` escape hatch allows reverting to peer-only evolution cleanly.

**`lifespan` and `games_since_last_reproduction` scale faster.** Heuristic games count toward both. With 2 peer and 2 heuristic games per tick, agents reach their reproduction interval and lifespan twice as fast as in Phase 8. This is intentional — more games per lifetime means faster fitness estimation and faster turnover — but `lifespan_range` may need upward adjustment if agents are dying before accumulating enough games to demonstrate their fitness.

## Dependencies

Builds on Phase 1 (`game/bots.py`, `game/match.py`), Phase 4/4b (tick loop, agent stats), Phase 5 (`population.rng` as the single reproducible RNG source — binding it into `heuristic_bot` is required for resume continuity, exactly as Phase 6 does for benchmark games), Phase 6 (nullable-agent-id `games` schema and `insert_game` invariant), and Phase 8 (game_type vocabulary, play_cli unaffected). No new external dependencies.
