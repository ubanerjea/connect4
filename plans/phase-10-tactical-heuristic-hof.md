# Phase 10 — Tactical Heuristic, Adaptive Weights, and Hall of Fame

*Phase 9 broke the Red Queen trap but created a new saturation problem: the heuristic win rate hit 1.0 by tick 500 and stayed there, removing all fitness gradient from the external challenge track. Agents learned offensive fork-creation but never defensive blocking, because the fixed heuristic bot never creates multi-step threats. Phase 10 addresses this on three fronts: a harder heuristic opponent that creates forks, adaptive fitness weights that respond to mastery level automatically, and a Hall of Fame that trains agents against their own best offensive patterns. See `evoconnect4_project_plan.md` §11.*

This document is a self-contained brief for entering the OpenSpec propose/apply cycle. It assumes Phases 0–9 are already built and archived — in particular Phase 9's two-track fitness formula, `_run_heuristic_challenges` mechanic, seven split counter columns, and `MUTABLE_FIELDS` extension pattern.

## Why

After 6000 ticks on Phase 9 (`mygame_02.db`):

- Heuristic benchmark win rate: **1.000 from tick 500 onwards**. The heuristic challenge provides zero differential fitness signal — all agents win virtually every game, so the heuristic track is a constant for everyone. Phase 9 solved the first 500 ticks, then the saturation dynamic returned.
- The best alive agent still fails to block the human's multi-step threats. The heuristic bot only creates 1-ply threats (immediate wins); agents learned to beat it by creating forks (two simultaneous threats the heuristic cannot block). They learned *offensive* multi-step thinking but never *defensive* recognition of the same.
- Peer games average 11.2 moves — an offensive arms race in which the faster attacker wins. The zero-sum peer dynamic rewards attacking, not defending; no selection pressure ever punished failing to block a developing threat.
- Random bot win rate is stable (~0.70 at the equivalent tick range), confirming agents are not fundamentally weaker — they are just locally optimized for a specific (now-saturated) challenge.

Three interlocking fixes:

1. **Upgrade the heuristic to tactical level.** Add fork creation and fork blocking to the heuristic's priority order. Agents cannot beat a fork-creating bot with pure offense; they must learn to prevent fork setups, which is precisely the defensive skill they lack.

2. **Make the challenge weights adaptive.** When the rolling benchmark heuristic win rate is high (mastery proven), shift weight from the heuristic track to the Hall of Fame track automatically. When a harder heuristic is deployed and win rate drops, weight shifts back. The fitness formula self-adjusts instead of requiring manual re-tuning.

3. **Introduce a Hall of Fame.** Keep the population's own past-best agents as a standing challenge pool. HoF agents already know how to create forks — they are exactly the kind of opponent that forces defensive learning. As the HoF grows stronger, the population must keep up.

## Scope

**In scope:**

1. `tactical_heuristic_bot` added to `game/bots.py`; a new `heuristic_bot_level` config param selects `"basic"` (Phase 9 behavior) or `"tactical"` (new).
2. Adaptive β_h and β_hof computed each tick from a rolling window of recent benchmark results, replacing the static `heuristic_fitness_weight` param.
3. Three-track fitness formula: peer, heuristic, Hall of Fame — weighted by adaptive β values that sum to exactly 1 with a fixed 0.3 peer weight.
4. `hall_of_fame` table in the schema; HoF member load/save machinery in the repository.
5. `Population._run_hof_challenges()` — per-tick games between every alive agent and randomly-sampled active HoF members, updating four new HoF counter columns.
6. `Population._run_hof_maintenance()` — unified entry and eviction event running every `hof_maintenance_every_n_ticks` ticks, evaluating HoF health and inducting/evicting as warranted.
7. Four new agent counter columns: `hof_wins`, `hof_draws`, `hof_games_played`, `hof_survival_credit`. Survival credit uses the shared `heuristic_survival_alpha`.
8. Three new `game_type` values: `hof_challenge`, `hof_maintenance_heuristic`, `hof_maintenance_peer`. The `insert_game` invariant is extended accordingly.
9. Fourteen new config params (plus one rename); all in `MUTABLE_FIELDS`.

**Out of scope:**

- "Both basic and tactical" parallel heuristic games. Phase 10 replaces the bot via `heuristic_bot_level`; running both in parallel is deferred.
- Analytics chart changes for the new fitness tracks or HoF history — the data is fully queryable from the DB.
- `population_snapshots` columns — unchanged.
- Structural genome mutation (§13) — independent concern.

## Design

### Tactical heuristic bot

`tactical_heuristic_bot` replaces `heuristic_bot` as the evolution challenge opponent when `heuristic_bot_level: tactical`. The signature is identical (`board: Board, rng=None → int`) and the existing Phase 6 `functools.partial(heuristic_bot, rng=self.rng)` binding pattern is unchanged — only the function swapped in.

Priority order (four rules, same as Phase 9's three plus two new ones inserted between rule 2 and the center preference):

```
1. Win immediately            -- if I can complete four-in-a-row this move, do it
2. Block opponent's 1-ply win -- if opponent can complete four-in-a-row next move, block it
3. Create a fork              -- [NEW] move that gives me >= 2 simultaneous winning threats
4. Block opponent's fork      -- [NEW] move opponent could play to give them >= 2 winning threats
5. Prefer center column       -- unchanged
```

Fork detection: for a candidate column `c` and player `p`, simulate dropping at `c`, then count legal columns where `board.would_win(col, p)` is true (excluding `c` itself). If count >= 2, column `c` creates a fork for player `p`. This is O(7 × 7) = O(49) `would_win` checks per candidate, vs. the current O(7). Stays fast; the inner simulation is a single list append/pop, identical to how `would_win` already works.

```
tactical_heuristic_bot pseudocode:

legal = board.legal_moves()
me = board.current_player;  opp = -me

# 1. Win immediately
winning = [c for c in legal if board.would_win(c, me)]
if winning: return choice(winning)

# 2. Block opponent's 1-ply win
blocking = [c for c in legal if board.would_win(c, opp)]
if blocking: return choice(blocking)

# 3. Create a fork
def threats_after(col, player):
    board._grid[col].append(player)
    try:
        return sum(1 for c in board.legal_moves()
                   if c != col and board.would_win(c, player))
    finally:
        board._grid[col].pop()

fork_creating = [c for c in legal if threats_after(c, me) >= 2]
if fork_creating: return choice(fork_creating)

# 4. Block opponent's fork
fork_blocking = [c for c in legal if threats_after(c, opp) >= 2]
if fork_blocking: return choice(fork_blocking)

# 5. Center preference (unchanged)
center = (board.columns - 1) / 2
nearest = [c for c in legal if abs(c - center) == min(abs(c - center) for c in legal)]
return choice(nearest)
```

`heuristic_bot_level: basic` selects the original three-rule bot, reproducing Phase 9 behavior identically. All other mechanics (game structure, counters, game_type label, etc.) are unchanged — the bot swap is purely in `_run_heuristic_challenges`'s choice of function.

---

### Adaptive fitness weights

`heuristic_fitness_weight` (the static β from Phase 9) is replaced by two adaptive values computed at the start of each `_recompute_fitness()` call from the rolling benchmark history. Nothing is stored in simulation state — the values are derived fresh each tick from the benchmark table, which is always up to date.

**Rolling window:**

```
recent_wins = SELECT win_rate FROM benchmark_results
              WHERE opponent_type = 'heuristic'
              ORDER BY tick DESC
              LIMIT heuristic_weight_adapt_window
```

If zero rows: `rolling_wr = 0.0` (use max weight — no mastery proven).
If 1..W rows: average whatever is available.

**Weight formula:**

```
t = clamp(
    (rolling_wr - heuristic_weight_adapt_low) /
    (heuristic_weight_adapt_high - heuristic_weight_adapt_low),
    0.0, 1.0
)

beta_h   = heuristic_fitness_weight_max - t * (heuristic_fitness_weight_max - heuristic_fitness_weight_min)
beta_hof = t * hof_fitness_weight_max          # 0.0 if hof is empty (no active members)
beta_peer = 1.0 - beta_h - beta_hof            # always 0.3 at default param values
```

With defaults (`beta_h_max=0.7`, `beta_h_min=0.3`, `beta_hof_max=0.4`):

```
rolling_wr   t     beta_h  beta_hof  beta_peer  sum
< 0.60       0.0   0.70    0.00      0.30       1.00  (Phase 9 regime)
  0.75       0.5   0.50    0.20      0.30       1.00
> 0.90       1.0   0.30    0.40      0.30       1.00  (full HoF regime)
```

When the heuristic bot is upgraded from `basic` to `tactical`, win rate drops from ~1.0 to some lower value. The weight formula responds automatically: `t` falls, `beta_h` rises back toward 0.70, `beta_hof` shrinks. The selection pressure re-engages against the heuristic with no manual re-tuning. Similarly, once agents master the tactical bot, the weight shifts back toward HoF.

`beta_hof` is hard-zero when the HoF has no active members, regardless of `t`, because there are no HoF games to score against.

**Three-track fitness formula:**

```
peer_fitness = (peer_wins + 0.5 * peer_draws) / peer_games_played
               if peer_games_played > 0 else 0.0

heuristic_fitness = (heuristic_wins + 0.5 * heuristic_draws + heuristic_survival_credit)
                    / heuristic_games_played
                    if heuristic_games_played > 0 else 0.0

hof_fitness = (hof_wins + 0.5 * hof_draws + hof_survival_credit) / hof_games_played
              if hof_games_played > 0 else 0.0

overall_fitness = beta_peer * peer_fitness + beta_h * heuristic_fitness + beta_hof * hof_fitness
```

Survival credit on HoF losses uses the shared `heuristic_survival_alpha`:
`hof_survival_credit += alpha * result.num_moves / (board_columns * board_rows)`

This is the same mechanism as Phase 9's heuristic survival credit. It provides a gradient when HoF members are much stronger than the current population (all agents lose, survival credit is the only differentiator).

---

### Hall of Fame

#### Schema

New table `hall_of_fame`:

```sql
CREATE TABLE IF NOT EXISTS hall_of_fame (
    id INTEGER PRIMARY KEY,
    agent_id INTEGER NOT NULL,           -- references agents.agent_id (genome is there)
    inducted_tick INTEGER NOT NULL,
    evicted_tick INTEGER,                -- NULL while active
    status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'evicted'
    heuristic_win_rate REAL NOT NULL DEFAULT 0.0,   -- updated at each maintenance
    internal_score REAL NOT NULL DEFAULT 0.0,       -- win rate within HoF, updated at maintenance
    combined_score REAL NOT NULL DEFAULT 0.0        -- 0.5*heuristic_win_rate + 0.5*internal_score
)
```

HoF members reference `agents.agent_id`. Dead agents are never deleted from the `agents` table, so the genome (stored in `agents.nn_weights`) remains loadable indefinitely. The HoF never stores a second copy of the genome; it only stores the reference and the maintenance-derived quality metrics.

Four new columns on the `agents` table:

```sql
hof_wins               INTEGER NOT NULL DEFAULT 0,
hof_draws              INTEGER NOT NULL DEFAULT 0,
hof_games_played       INTEGER NOT NULL DEFAULT 0,
hof_survival_credit    REAL NOT NULL DEFAULT 0.0
```

These accumulate on **living agents only** (from per-tick HoF challenge games). Dead HoF members are never updated by these columns after death; their role in the system is purely as opponents.

#### Per-tick HoF challenges

Each tick, after heuristic challenges and before `_recompute_fitness()`, every alive agent plays `hof_games_per_agent_per_tick` games against randomly-sampled active HoF members (sampled with replacement if the HoF has fewer members than `hof_games_per_agent_per_tick`). If the HoF has no active members, this step is skipped entirely.

```
_run_hof_challenges() pseudocode:

IF NOT hof_enabled OR hof is empty: return

active_hof = repo.list_hof_agents(status='active')  -- reconstructed as Agent objects
alpha = config.heuristic_survival_alpha
board_cells = board_columns * board_rows

FOR agent IN self.alive:
    FOR i IN range(hof_games_per_agent_per_tick):
        first_mover = 1 if i % 2 == 0 else -1
        hof_member = rng.choice(active_hof)  -- sample with replacement
        result = play_match(agent.choose_move, hof_member.choose_move, first_mover=first_mover)

        IF result.winner == 1:
            agent.hof_wins += 1;  agent.wins += 1
            db_result = "player1_win"
        ELIF result.winner == -1:
            agent.hof_survival_credit += alpha * result.num_moves / board_cells
            agent.losses += 1
            db_result = "player2_win"
        ELSE:
            agent.hof_draws += 1;  agent.draws += 1
            db_result = "draw"

        agent.hof_games_played += 1
        agent.games_played += 1
        agent.games_since_last_reproduction += 1

        repo.insert_game(
            tick=self.tick,
            player1_agent_id=agent.agent_id,
            player2_agent_id=hof_member.agent_id,
            result=db_result,
            num_moves=result.num_moves,
            move_history=result.move_history,
            game_type="hof_challenge",
        )
        self._persist_stats(agent)
```

Per-tick HoF challenge games DO count toward living agent `games_played` and `games_since_last_reproduction`. The lifespan acceleration note from Phase 9's risks section applies: with 2 peer + 2 heuristic + 2 HoF games per tick, agents accumulate game counts 3× faster than Phase 8. Monitor `lifespan_range` accordingly.

#### HoF maintenance (entry + eviction)

Runs on every tick where `self.tick % hof_maintenance_every_n_ticks == 0`. Entry and eviction are a single unified event — there is no separate entry-checking at other tick intervals.

```
_run_hof_maintenance() pseudocode:

IF NOT hof_enabled: return
IF self.tick % hof_maintenance_every_n_ticks != 0: return
IF self.alive is empty: return

bound_heuristic = functools.partial(heuristic_bot_fn, rng=self.rng)
active_hof = repo.list_hof_agents(status='active')   -- may be empty

-- STEP 1: Re-evaluate each existing member vs heuristic bot
FOR member IN active_hof:
    wins = draws = 0
    FOR i IN range(hof_maintenance_heuristic_games):
        first_mover = 1 if i % 2 == 0 else -1
        result = play_match(member.choose_move, bound_heuristic, first_mover=first_mover)
        log game as game_type='hof_maintenance_heuristic', player1=member.agent_id, player2=None, opponent_label='heuristic'
        wins += (result.winner == 1); draws += (result.winner == 0)
    member_heuristic_wr = (wins + 0.5 * draws) / hof_maintenance_heuristic_games
    repo.update_hof_heuristic_win_rate(member.id, member_heuristic_wr)

-- STEP 2: Intra-HoF pairing (random pairs, each pair plays hof_maintenance_peer_games games)
FOR each pair (ma, mb) IN random_pairs(active_hof):
    FOR i IN range(hof_maintenance_peer_games):
        first_mover = 1 if i % 2 == 0 else -1
        result = play_match(ma.choose_move, mb.choose_move, first_mover=first_mover)
        log game as game_type='hof_maintenance_peer', player1=ma.agent_id, player2=mb.agent_id
        update win accumulators for ma and mb

-- aggregate internal_score per member = (intra_wins + 0.5*intra_draws) / intra_games_played
-- combined_score = 0.5 * heuristic_win_rate + 0.5 * internal_score
-- repo.update_hof_scores(member.id, internal_score, combined_score) for each member

-- STEP 3: Evaluate candidate (current best-alive by fitness)
candidate = max(self.alive, key=lambda a: a.fitness)
c_wins = c_draws = 0
FOR i IN range(hof_entry_series_games):   -- uses hof_maintenance_heuristic_games
    first_mover = 1 if i % 2 == 0 else -1
    result = play_match(candidate.choose_move, bound_heuristic, first_mover=first_mover)
    c_wins += (result.winner == 1); c_draws += (result.winner == 0)
candidate_wr = (c_wins + 0.5 * c_draws) / hof_maintenance_heuristic_games

-- STEP 4: Entry / eviction decision
IF candidate_wr >= hof_entry_heuristic_threshold:
    IF len(active_hof) < hof_max_size:
        -- Hall has room: induct immediately
        repo.induct_hof(candidate.agent_id, self.tick, heuristic_win_rate=candidate_wr)
    ELSE:
        -- Hall is full: check if candidate earns a slot
        weakest = min(active_hof, key=lambda m: m.combined_score)
        IF candidate_wr >= weakest.heuristic_win_rate + hof_eviction_margin:
            repo.evict_hof(weakest.id, self.tick)
            repo.induct_hof(candidate.agent_id, self.tick, heuristic_win_rate=candidate_wr)
        -- else: candidate does not clear the bar; hall unchanged this cycle
```

**Key invariants of the maintenance mechanic:**

- Maintenance games (Steps 1 and 2) do NOT increment living agent `games_played` or `games_since_last_reproduction`. They only update `hall_of_fame` table fields. Dead HoF members playing games in Steps 1–2 cannot reproduce or age out.
- Candidate evaluation (Step 3) also does NOT update the living candidate's counters — it is a one-off probe, not part of the evolutionary record. The result feeds only the entry decision.
- Induction does not mutate the inducted agent's genome or alter its live counters. The HoF stores a reference only; the agent continues evolving normally in the live pool.
- A candidate can be the same agent as an active HoF member (if they are still alive). This is harmless — the induction call would insert a duplicate reference, which should be guarded against (check agent_id not already active in HoF before inducting).

---

### Where in `run_tick()` this executes

```
run_tick():
    self.tick += 1
    peer games              -- unchanged; updates peer track + unified totals
    heuristic challenges    -- Phase 9; bot selected by heuristic_bot_level
    hof challenges          -- NEW; updates hof track + unified totals; skipped if hof empty
    _recompute_fitness()    -- three-track formula with adaptive betas; same call site
    reproduction/death loop -- unchanged; uses overall_fitness
    _run_benchmark()        -- unchanged; writes benchmark_results used by adaptive formula next tick
    _run_hof_maintenance()  -- NEW; runs only on maintenance ticks; updates hall_of_fame table
    _write_snapshot()       -- unchanged
    repo.commit()           -- unchanged
```

`_recompute_fitness()` queries the benchmark table for the rolling window before the current tick's benchmark result is written (benchmark runs after). This is the correct causal ordering — the adaptive weights for tick N are computed from ticks 0..N-1, not from N itself.

`_run_hof_maintenance()` runs after `_run_benchmark()` so that if this is also a benchmark tick, the fresh benchmark result is committed before the maintenance candidate evaluation. In practice the maintenance queries the heuristic win rate from the live counters computed during Step 3, not from the benchmark table, so the ordering is not critical — but placing maintenance last keeps the semantic clear.

---

### Config changes

`heuristic_fitness_weight` (Phase 9) is **renamed** to `heuristic_fitness_weight_max` and joined by the following new parameters. All are `MUTABLE_FIELDS`.

| Parameter | Default | Description |
|---|---|---|
| `heuristic_bot_level` | `"tactical"` | `"basic"` selects the Phase 9 three-rule bot; `"tactical"` adds fork creation/blocking (rules 3–4). |
| `heuristic_fitness_weight_max` | `0.7` | Renamed from `heuristic_fitness_weight`. Maximum β_h, used when rolling heuristic win rate is below `adapt_low`. |
| `heuristic_fitness_weight_min` | `0.3` | Floor for β_h. Never drops below this regardless of win rate. |
| `heuristic_weight_adapt_low` | `0.60` | Rolling win rate below this threshold → β_h stays at max. |
| `heuristic_weight_adapt_high` | `0.90` | Rolling win rate above this threshold → β_h falls to min. |
| `heuristic_weight_adapt_window` | `20` | Number of most-recent benchmark results (vs. heuristic) used to compute rolling win rate. |
| `hof_enabled` | `true` | Set `false` to disable all HoF logic (challenges, maintenance, fitness). HoF track is silent; weights degrade to peer + heuristic only. |
| `hof_max_size` | `20` | Maximum active HoF members. |
| `hof_games_per_agent_per_tick` | `2` | Games each alive agent plays against a random active HoF member per tick. `0` disables per-tick HoF challenges without disabling maintenance. |
| `hof_maintenance_every_n_ticks` | `50` | Frequency of the unified entry/eviction maintenance event. |
| `hof_maintenance_heuristic_games` | `20` | Games each HoF member (and each candidate) plays vs. heuristic bot during maintenance. Also the entry series length. |
| `hof_maintenance_peer_games` | `4` | Games per matched pair within HoF during intra-HoF maintenance play. |
| `hof_entry_heuristic_threshold` | `0.70` | Candidate must win this fraction of `hof_maintenance_heuristic_games` games vs. heuristic to be eligible for induction. |
| `hof_eviction_margin` | `0.15` | Candidate must exceed the weakest member's `heuristic_win_rate` by at least this margin to trigger eviction. Prevents cycling when the hall and population are similar in strength. |
| `hof_fitness_weight_max` | `0.4` | Ceiling for β_hof. Reached when `t = 1.0` (rolling win rate ≥ `adapt_high`). With defaults, β_peer = 1 − 0.3 − 0.4 = 0.3 at max HoF weight. |

`heuristic_fitness_weight: 0.7` is **removed** from `config.yaml`; `heuristic_fitness_weight_max: 0.7` replaces it. A resume with the old key must be handled gracefully in `config.py` (either alias it or emit a clear error pointing to the rename).

---

### `games` table and `insert_game` invariant

Three new `game_type` values, extending the Phase 9 invariant:

| `game_type` | `player1_agent_id` | `player2_agent_id` | `opponent_label` |
|---|---|---|---|
| `'evolution'` | NOT NULL | NOT NULL | NULL |
| `'benchmark'` | NOT NULL | NULL | NOT NULL |
| `'human_vs_agent'` | NOT NULL | NULL | NOT NULL |
| `'evolution_heuristic'` | NOT NULL | NULL | `'heuristic'` |
| `'hof_challenge'` *(new)* | NOT NULL (living agent) | NOT NULL (HoF agent_id) | NULL |
| `'hof_maintenance_heuristic'` *(new)* | NOT NULL (HoF agent_id) | NULL | `'heuristic'` |
| `'hof_maintenance_peer'` *(new)* | NOT NULL (HoF agent_id) | NOT NULL (HoF agent_id) | NULL |

`hof_maintenance_heuristic` and `hof_maintenance_peer` have no effect on the living population's fitness counters; they are logged for analytics and auditability (which HoF members played whom, what their maintenance scores were).

---

### `run_simulation.py` MUTABLE_FIELDS

`heuristic_fitness_weight` is removed (renamed). Added:

```python
MUTABLE_FIELDS = (
    ...existing Phase 9 fields (minus heuristic_fitness_weight)...
    "heuristic_bot_level",              # new
    "heuristic_fitness_weight_max",     # renamed from heuristic_fitness_weight
    "heuristic_fitness_weight_min",     # new
    "heuristic_weight_adapt_low",       # new
    "heuristic_weight_adapt_high",      # new
    "heuristic_weight_adapt_window",    # new
    "hof_enabled",                      # new
    "hof_max_size",                     # new
    "hof_games_per_agent_per_tick",     # new
    "hof_maintenance_every_n_ticks",    # new
    "hof_maintenance_heuristic_games",  # new
    "hof_maintenance_peer_games",       # new
    "hof_entry_heuristic_threshold",    # new
    "hof_eviction_margin",              # new
    "hof_fitness_weight_max",           # new
)
```

---

### Compute cost

| Source | Games per tick (steady state, defaults) | Notes |
|---|---|---|
| Peer games | ~500×249/500 ≈ 500 | half the population pairs, 2 games each |
| Heuristic challenges | 500 × 2 = 1,000 | unchanged from Phase 9 |
| HoF challenges | 500 × 2 = 1,000 | once HoF has ≥ 1 member |
| HoF maintenance (amortized) | 1,180 / 50 ≈ 24 | 20 members × 20 heuristic + ~190 intra-HoF pair games |
| **Total** | **~2,524** | ~2× Phase 9, ~5× Phase 8 |

HoF maintenance games are not forward passes for living agents (only for frozen HoF members), but they are still `play_match` calls. The per-50-tick burst is ~1,200 games on maintenance ticks. Reduce `hof_maintenance_heuristic_games` to 10 or `hof_maintenance_peer_games` to 2 if wall-clock time is a constraint.

---

## Files changed

| File | Change |
|---|---|
| `config.yaml` | Rename `heuristic_fitness_weight` → `heuristic_fitness_weight_max`; add 14 new params |
| `src/evoconnect4/config.py` | Add 14 new fields to `Config` dataclass; handle rename with graceful error or alias |
| `src/evoconnect4/game/bots.py` | Add `tactical_heuristic_bot`; add `get_heuristic_bot(level)` selector |
| `src/evoconnect4/storage/schema.py` | Add `hall_of_fame` table DDL; add 4 new columns to `agents` DDL |
| `src/evoconnect4/storage/repository.py` | Add `insert_hof`, `list_hof_agents`, `update_hof_heuristic_win_rate`, `update_hof_scores`, `evict_hof`; update `insert_agent`, `update_agent_stats`, `get_agent`, `list_agents` for 4 new columns; extend `insert_game` invariant with 3 new game types |
| `src/evoconnect4/agent/agent.py` | Add `hof_wins`, `hof_draws`, `hof_games_played`, `hof_survival_credit` counter fields |
| `src/evoconnect4/evolution/population.py` | Add `_run_hof_challenges()`; add `_run_hof_maintenance()`; update `_recompute_fitness()` for 3-track adaptive formula; call both new methods from `run_tick()`; update `load()` to restore 4 new counters |
| `src/evoconnect4/run_simulation.py` | Update `MUTABLE_FIELDS`; handle `heuristic_fitness_weight` rename on resume |

No changes to `game/match.py`, `game/connect_four.py`, `interface/play_cli.py`, or `analytics/plots.py`.

---

## Definition of done

- `heuristic_bot_level: basic` reproduces Phase 9 behavior identically: identical RNG state at tick-end, identical game counts, identical fitness values for a controlled run.
- `tactical_heuristic_bot` creates a fork when one is available and blocks opponent's fork setup when no fork of its own exists: unit test provides a board position with a clear fork column and confirms the bot selects it; a second test confirms it blocks opponent's fork setup.
- Adaptive weight formula: `_recompute_fitness` computes correct β_h and β_hof for known `rolling_wr` values — unit test checks (rolling_wr=0.0, t=0.0, β_h=0.70, β_hof=0.00), (rolling_wr=0.75, t=0.5, β_h=0.50, β_hof=0.20), (rolling_wr=1.0, t=1.0, β_h=0.30, β_hof=0.40). All sum to 1.0 with β_peer=0.30.
- Empty HoF: β_hof is 0.0 regardless of `t`; `_run_hof_challenges` exits immediately; `_run_hof_maintenance` induction path runs normally but HoF challenges are skipped. The 2-track Phase 9 formula is reproduced exactly.
- `hall_of_fame` table is created in a fresh DB; can be added to an existing Phase 9 DB via `CREATE TABLE IF NOT EXISTS` (schema migration). Four new agent columns are added via `ALTER TABLE agents ADD COLUMN ... DEFAULT 0` when the column does not exist.
- Maintenance games (`hof_maintenance_heuristic`, `hof_maintenance_peer`) do NOT increment any living agent's `games_played` or `games_since_last_reproduction`: confirmed by a controlled run where tick-by-tick living-agent game counts match expected values with and without maintenance ticks.
- Per-tick HoF challenge games (`hof_challenge`) DO increment `games_played` and `games_since_last_reproduction`: confirmed by inspection of agent counters after a controlled tick.
- `hof_challenge` game records have non-NULL `player1_agent_id` (living agent) and non-NULL `player2_agent_id` (HoF member); `insert_game` invariant enforces this.
- Entry: a candidate with `candidate_wr >= hof_entry_heuristic_threshold` is inducted when the hall has room. A candidate with `candidate_wr < hof_entry_heuristic_threshold` is not inducted regardless of HoF state.
- Eviction: when the hall is full, a candidate is inducted and the weakest member is evicted only when `candidate_wr >= weakest.heuristic_win_rate + hof_eviction_margin`. When this condition is not met, the hall is unchanged.
- `Population.load()` correctly restores all four new HoF agent counters; active HoF members are reconstructed as Agent objects (from `agents.nn_weights`) and held ready for per-tick challenge sampling.
- Over a multi-thousand-tick run with `heuristic_bot_level: tactical`, benchmark heuristic win rate starts lower than the Phase 9 baseline (confirming the tactical bot is harder) and shows a rising trend as the population adapts. Adaptive weights shift accordingly — observable by querying the rolling window at various tick checkpoints.
- Full existing test suite passes.

---

## Risks and mitigations

**Tactical heuristic is too hard for a long time.** If the population cannot make progress against the fork-creating bot, survival credit keeps differentiating agents but no one accumulates wins. The adaptive weight responds correctly (β_h stays high), but the fitness landscape may flatten if all survival credits converge. Mitigation: reduce `heuristic_fitness_weight_min` to 0.2 to give peer games more room; or temporarily switch back to `heuristic_bot_level: basic` while the population recovers.

**HoF cold start creates a period with no HoF games.** For the first `hof_maintenance_every_n_ticks` ticks (50 by default), the HoF is empty and β_hof = 0. This is Phase 9 behavior exactly — not a regression, just a delayed start. If continuity with mygame_02 is desired, the first maintenance event will find that the current best alive agent is a strong candidate, so the HoF fills immediately after tick 50.

**HoF lock.** If all active HoF members clear their eviction margin, no new entries happen even if the population has improved substantially. Symptom: HoF `heuristic_win_rate` values are all high (> 0.8) and stagnant. Mitigation: reduce `hof_eviction_margin` on resume (e.g., from 0.15 to 0.05). The margin exists to prevent thrashing, not permanent lock.

**HoF members become irrelevant over many thousands of ticks.** Very old HoF members from early ticks may have `heuristic_win_rate < entry_threshold` after many maintenance cycles and eventually get evicted. This is expected and correct behavior — the hall continuously improves.

**Lifespan pressure with 3× games.** With 2 peer + 2 heuristic + 2 HoF games per tick (steady state), agents accumulate game counts faster than Phase 8 (3×) and Phase 9 (1.5× additional from HoF). Agents may reach their lifespan ceiling or reproduction interval too quickly for fitness to stabilize. If agents are dying very young relative to lifespan, increase `lifespan_range` (e.g., `[100, 300]`) or increase `reproduction_interval_min` so agents need more game experience before reproducing.

**Candidate evaluated vs. heuristic only, not vs. HoF.** The entry decision is based on the candidate's heuristic win rate alone. A candidate could pass the threshold while being weak against current HoF members. This is a deliberate simplification — the intra-HoF games after induction will correctly assign them a low `internal_score`, making them the weakest member by `combined_score` and first in line for eviction at the next maintenance cycle. Self-correcting.

---

## Dependencies

Builds on Phase 9 (two-track fitness formula, `_run_heuristic_challenges`, `heuristic_survival_alpha`, `evolution_heuristic` game type, `MUTABLE_FIELDS` extension pattern), Phase 6 (nullable-agent-id `games` schema, `insert_game` invariant, `functools.partial` bot binding), Phase 5 (RNG-state persistence — HoF member choosers are deterministic and do not touch `self.rng`; only the living-agent games use `self.rng`, maintaining resume continuity), and Phase 1 (`bots.py`, `connect_four.Board.would_win`). No new external dependencies.
