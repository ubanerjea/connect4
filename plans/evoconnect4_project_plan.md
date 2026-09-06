# EvoConnect4 — Project Plan

*Evolving neural-network agents to play Connect Four, using genetic algorithms instead of gradient descent.*

## At a Glance

| | |
|---|---|
| **Game** | Connect Four (7×6), turn-based, two-player adversarial |
| **Agent brain** | Small feedforward neural network (~1,200 weights) — evolved, never trained by gradient |
| **Evolution style** | Steady-state "living population": individual birth, reproduction, and death — not synchronized generations |
| **Genome** | NN weights + lifespan + self-adaptive mutation rate + crossover rate (structure reserved for a later phase) |
| **Fitness** | Win rate within the population, cross-checked against fixed baseline opponents |
| **Storage** | SQLite: agents, games, population snapshots, benchmark results |
| **Language** | Python 3 + numpy (network) + SQLite (storage) |
| **Human play** | Terminal CLI against any saved agent, e.g. "current best" |

## Table of Contents

1. Overview
2. The Game: Connect Four
3. Agents: Neural Network & Genome
4. Evolutionary Model: A Living Population
5. Fitness Function
6. Database Design
7. Software Architecture & Project Structure
8. Human-vs-Agent Interface
9. Analytics
10. Configuration Reference
11. Development Roadmap
12. Definition of Done (MVP)
13. Possible Extensions
14. Risks & Things to Watch

---

## 1. Overview

This project builds a small, closed ecosystem: a population of neural-network-driven agents that learns to play Connect Four purely through evolution. There is no backpropagation and no reinforcement-learning gradient anywhere in the loop — an agent's neural network weights are entirely a *phenotype*, expressed from its genome and used to make decisions, but never directly adjusted. The only source of improvement, over time, is selection, mutation, and (optionally) crossover acting on the population as a whole.

Two design threads run through everything below:

1. **The game and the agent's brain** — a simple, adversarial, non-trivial game (§2) and a small feedforward network that reads the board and picks a move (§3).
2. **The population dynamics** — because the spec ties reproduction and death to *individual* counters (an agent's own lifespan in games, its own reproduction interval derived from its own fitness) rather than to synchronized generations, this plan uses a **steady-state, continuously-running population** — closer to a small artificial-life simulation than a textbook generational genetic algorithm. Agents are born, play, reproduce, and die on their own schedules while sharing one live pool (§4).

Everything is persisted to a SQLite database (§6) as it happens, so the whole run — every agent, every game, every birth and death — is queryable afterward for analytics (§9).

---

## 2. The Game: Connect Four

### Why Connect Four

- **Turn-based and deterministic** — no timing, physics, or simultaneous-move edge cases to get right; a "move" is just "which column."
- **Two-player adversarial by nature** — there's no way to play it against "the environment"; every game is agent vs. agent (or agent vs. human).
- **Small, clean action space** — only 7 possible moves (columns) at any time, versus e.g. up to 42 or 64 cells in some alternatives. A smaller action space means the network's output layer is tiny and the evolutionary search is more tractable — genomes converge on something coherent faster, which matters for a toy project's compute budget.
- **Compact board representation** — 42 cells map cleanly onto a fixed-size input vector.
- **Quick to implement** — board, legal-move check, and win detection (four in a row, in any of four directions) is comfortably a few hundred lines with no external dependencies.
- **A proven testbed** — Connect Four shows up repeatedly in both classical game-tree search and neuro-evolution work, so there's a lot of intuition (and sanity-checking opportunity) available if evolved agents start behaving strangely.

### Why it clears the "not obviously trivial" bar

Connect Four is technically a *solved* game — with perfect play, the first player wins by starting in the center column, a result reached via exhaustive computer search in 1988. That can sound disqualifying at first glance, but the character of the solution matters: it's a deep lookup structure built from millions of positions, not a one-line insight a person (or a small evolved network) stumbles into by inspection. That's the real difference from tic-tac-toe, which anyone can fully solve in their head via symmetry in a couple of minutes, or one-shot Prisoner's Dilemma, where the dominant strategy is a single sentence. Short of that deep, hard-won solution, Connect Four has a rich space of tactics — odd/even threats, forks, tempo — for evolution to discover partially, which is exactly the interesting middle ground a toy project wants: not trivial, not intractable.

### Rules, briefly

- Board: 7 columns × 6 rows.
- Players alternate dropping a disc into any non-full column; gravity carries it to the lowest empty cell in that column.
- First player to connect four discs in a row — horizontally, vertically, or diagonally (either direction) — wins immediately.
- A full board with no winner is a draw.

### Alternatives considered

Noted for the record — the game engine (§7) sits behind a small, isolated interface, so swapping games later doesn't require touching the agent or evolution code:

- **Othello/Reversi** — richer positional play (corners, edges), but a larger action space (up to 64 cells) and the flip-captured-pieces rule adds more implementation complexity than Connect Four's simple gravity-drop.
- **Grid-based Tron / light cycles** — fun, visual, genuinely satisfies "real-time but very easy" — but simultaneous moves mean deciding what happens when both players move into the same cell on the same tick, plus a max-length draw rule for games that run long; a few more edge cases than Connect Four's strictly-one-mover-at-a-time model.

### Headless by design, human-playable on top

The rules engine (`connect_four.py`) is pure logic with zero I/O — board state in, legal moves and win/draw checks out — so it can silently play thousands of games during evolution without ever touching a screen. The CLI (§8) is a thin, separate layer that renders that same board as text and reads a human's column choice; it calls the identical rules engine a running evolution uses. That separation is what makes "headless" and "human-playable" simultaneously easy instead of a trade-off.

---

## 3. Agents: Neural Network & Genome

### 3.1 What the network sees and does

**Input (42 values):** the board is encoded from the perspective of whichever agent is about to move — its own discs as `+1`, the opponent's as `-1`, empty cells as `0`. This relative encoding means the same set of weights plays correctly whether the agent happens to be seated first or second in a given match; without it, the network would effectively have to learn two separate strategies (as mover 1 and as mover 2) rather than one.

**Output (7 values):** one raw score per column. Full columns are masked to `-∞` before choosing, and the MVP behavior is to simply pick the highest-scoring legal column (deterministic — useful for reproducible evaluation). A stochastic variant (softmax over legal columns, sampled by an evolvable "temperature" trait) is a natural, optional extension noted in §3.2.

**Architecture:** a single hidden layer by default (e.g. 24 neurons, `tanh` activation — bounded, which keeps things well-behaved under random weight mutation), linear output layer. At 42 inputs → 24 hidden → 7 outputs, that's roughly 1,200 weights and biases total — small enough to evolve quickly, large enough to express non-trivial behavior.

**No backpropagation, ever.** The network is a pure phenotype: it's built fresh from a genome's weight vector, used to play games, and then discarded (or reproduced from) — nothing about its weights is ever adjusted by a gradient. All improvement happens at the population level, across generations.

### 3.2 Genome layout

| Gene | What it controls | How it mutates |
|---|---|---|
| **NN weights** | Every weight & bias in the network (flattened to one vector) | Gaussian noise added to every weight, `N(0, σ²)`, where σ is the agent's own mutation-rate gene below |
| **NN architecture** *(reserved)* | Hidden layer width(s) | Fixed at birth in the MVP; see §3.4 for the structural-mutation extension |
| **Lifespan** | How many (counted) games this agent gets to play before it dies | Multiplicative Gaussian step (±~10%), clamped to a configured range |
| **Mutation rate (σ)** | The strength of weight mutation, above | *Self-adaptive*: mutates itself via a log-normal update each time it's inherited, so evolution tunes its own exploration strength (see below) |
| **Crossover rate** | Probability this agent reproduces sexually (vs. cloning) when its turn comes | Small additive Gaussian step, clamped to [0, 1] |

**A note on self-adaptive mutation:** rather than fixing one mutation strength for the whole population forever, each agent carries its own σ, and that σ quietly mutates alongside everything else when it reproduces (`σ' = σ · e^{N(0, τ²)}`, clamped to a sane range). Lineages that happen onto a good σ — aggressive early, gentler later — simply tend to leave more successful descendants. It's a small, well-known trick from evolution-strategies research, and it means you don't have to hand-schedule mutation strength over the course of the run.

### 3.3 How reproduction builds a new genome

Every reproduction event (§4.3 covers *when* these happen) follows the same two steps:

1. **Combine.** With probability equal to the parent's own crossover_rate, pick a second parent via small tournament selection (sample e.g. 5 agents at random from the live population, take the fittest) and combine:
   - NN weights: **uniform crossover** — each weight independently inherited from parent A or parent B (50/50).
   - Trait genes (lifespan, mutation rate, crossover rate): the **average** of the two parents' values.

   Otherwise (probability `1 − crossover_rate`), the child's starting genome is simply a **clone** of the single parent.

2. **Mutate.** Mutation is applied *unconditionally* after step 1 — even a clone always gets mutated before becoming a new agent. This is what directly satisfies "genetic code accommodates random mutation when propagating to the next generation": there is no path from parent to offspring that skips it.

### 3.4 Room to grow: structure evolution

The spec calls for genetic code that can govern network *structure*, not just weights. The MVP keeps architecture fixed at birth (simplest to implement and reason about first), but the genome format reserves a slot for it from day one, so adding real structural mutation later — grow/shrink the hidden layer, add a second hidden layer, within configured bounds — doesn't require redesigning the genome, only extending the mutation operator. §13 discusses this further, including `neat-python` as an off-the-shelf alternative if you want to go all the way to full NEAT-style topology evolution.

---

## 4. Evolutionary Model: A Living Population

### 4.1 Why not classic generations

A standard genetic algorithm replaces the *entire* population at once, every generation, based on population-wide fitness ranking. That doesn't fit this spec: lifespan is framed as "die after a certain number of games" (an individual, per-agent countdown) and reproduction as happening "at intervals determined by fitness" (again, per-agent timing). So instead of discrete generations, this plan uses a **steady-state, continuously-running population** — one shared pool where each agent is born, plays, possibly reproduces more than once, and eventually dies, all on its own schedule.

### 4.2 The simulation tick

Time in the simulation advances in discrete **ticks** (not to be confused with a *turn* inside a single Connect Four game). Each tick:

```
FOR each tick:
    alive := agents currently alive
    shuffle(alive)
    pairs := consecutive pairs from alive        (odd one out sits out, or plays a benchmark game)

    FOR each pair (A, B):
        play two games: one with A moving first, one with B moving first
        update A and B's games_played / wins / losses / draws
        write both games to the games table

    FOR each agent in alive:
        recompute fitness = (wins + 0.5 x draws) / games_played
        IF games_since_last_reproduction >= reproduction_interval(fitness):
            build and add a child genome (§3.3), linked to its parent(s)
            reset games_since_last_reproduction to 0
        IF games_played >= lifespan:
            mark agent dead, remove from the active pool (record kept in DB)

    IF population count > capacity:
        cull the lowest-fitness agent among those old enough to judge fairly

    IF this is a benchmark tick:
        evaluate the current best agent against the fixed baseline opponents (§5)

    write a population snapshot (size, fitness stats, average gene values) to the DB
```

*(Pseudocode — an outline of the algorithm, not implementation.)*

### 4.3 Reproduction timing: tying frequency to fitness

The interval an agent must wait between reproductions is a direct, linear function of its own fitness:

```
reproduction_interval(fitness) = MAX_INTERVAL - fitness x (MAX_INTERVAL - MIN_INTERVAL)
```

clamped to `[MIN_INTERVAL, MAX_INTERVAL]`. With the defaults in §10 (`MIN=8`, `MAX=25`):

| Fitness | Reproduction interval (games) |
|---|---|
| 0.00 | 25 |
| 0.25 | 21 |
| 0.50 | 17 |
| 0.75 | 12 |
| 1.00 | 8 |

A struggling agent still gets a shot roughly every 25 games (nothing is ever permanently barred from reproducing), while a dominant one can reproduce as often as every 8 — the direct, literal reading of "reproduce at intervals determined by the fitness function." Note that `MIN_INTERVAL` doubles as a natural floor on sample size: no agent reproduces before it's played at least 8 games, so early reproduction decisions aren't made off one or two lucky/unlucky results.

### 4.4 Death

An agent dies the moment `games_played` reaches its own `lifespan` gene — a straightforward, individual countdown, exactly as specified. Dead agents are removed from the active pool (so they stop being paired for matches) but their full record stays in the database indefinitely — lineage, final stats, and all.

### 4.5 Keeping population size in check

Left alone, fitness-driven reproduction could grow the population indefinitely. This plan enforces a fixed carrying capacity: whenever a reproduction event would push the population over that cap, the **lowest-fitness agent** among those old enough to have a fair fitness estimate (i.e., past `MIN_INTERVAL` games — reusing the threshold from §4.3) is culled to make room. Very young agents are protected from this so nobody is judged and removed before they've had a fair chance.

*(Simpler alternative, if you'd rather not implement culling right away: just skip a reproduction event when at capacity, and let natural deaths free up room instead. Slower to reach steady population turnover, but one less mechanism to build.)*

### 4.6 Match pairing & the first-move-advantage problem

Each tick, the alive population is shuffled and paired up sequentially (an odd one out sits that tick out). Because Connect Four has a known first-player edge, each matched pair plays **two** games per tick — one with each agent moving first — so a pair's results reflect who played better, not just who happened to go first.

### 4.7 Senescence: a cost for longevity (a possible extension, not yet built — see §13)

As designed so far, `lifespan` is a purely dominant trait with no offsetting cost: a longer-lived agent gets strictly more ticks to hit `reproduction_interval(fitness)` repeatedly (§4.3) and strictly more chances to be sampled as a tournament-selection parent (§3.3), independent of whether its network is actually any good at Connect Four. Left alone, this is expected to pull the population toward maximum lifespan regardless of playing skill — exactly the "lifespan could pin at its ceiling" risk flagged in §14. The fix decided on (but not yet implemented — noted as a possible future extension in §13 rather than its own roadmap phase, since it's a small, self-contained addition rather than a full phase of work) is **somatic mutation**, distinct from the germline mutation already in §3.2:

- **Germline mutation** (§3.2, existing): happens only at reproduction, perturbs the *genome*, and is inherited by offspring.
- **Somatic mutation** (new): happens continuously during an agent's own life, perturbs only its *live, in-play weights* — a copy, separate from the stored genome — and is **never inherited**. The biological parallel is exact, not just a loose metaphor: somatic mutations accumulate in an organism's body over its life (it's literally why cancer risk rises with age) without ever reaching the germ line.

Mechanically: once an agent passes some fraction of its own `lifespan` (a threshold), its live weights start accumulating Gaussian noise — reusing the same weight-mutation math §3.2 already defines, just applied to a live copy instead of producing a new genome — with the rate/magnitude accelerating the further past that threshold the agent gets. Because these mutations are undirected (no gradient or fitness feedback informs them, per §3.1's "no backpropagation, ever"), and because random perturbation in a ~1,200-dimensional weight space is overwhelmingly more likely to degrade task performance than improve it absent such guidance, this reliably produces decay, not a random walk in either direction.

This closes the loop through mechanics the plan already has, with no new machinery: since fitness is a win-rate over *all* games played (§5), degraded late-life performance drags an agent's own fitness down, which lengthens its `reproduction_interval` (§4.3) and makes it a more likely culling target (§4.5) — so a long lifespan now comes with rising risk, not a free lunch.

`Agent` (Phase 2) intentionally does **not** carry this. Phase 4 extends `Agent` with live-stats (games_played, wins, losses, draws, fitness, games_since_last_reproduction) to run the core evolutionary loop, but still does not add mutable live weights for this — see §13 if this extension is ever pursued.

---

## 5. Fitness Function

```
fitness = (wins + 0.5 x draws) / games_played
```

Simple, bounded to `[0, 1]`, and computed only from games that count officially — matches against other live agents during a tick. Human-exhibition games (§8) and benchmark games (below) are logged for the record but deliberately excluded from this calculation, so casual play sessions or evaluation runs never distort an agent's official standing.

**A caveat worth taking seriously:** because fitness here is measured entirely *against the current population*, it's a relative, co-evolving signal — a population can plateau or even quietly cycle (get better at beating each other without getting better at the game itself, a classic "Red Queen" effect in co-evolution) while internal fitness numbers look fine. The fix is to periodically check progress against something that doesn't co-evolve:

- **Fixed baseline opponents**, run on a schedule (default every 10 ticks, §10) against the current best live agent:
  - A **pure random mover** (picks any legal column uniformly at random) — the floor.
  - A **simple heuristic bot**: win immediately if a winning move exists → otherwise block the opponent's immediate winning move if one exists → otherwise prefer columns closer to the center → ties broken randomly. Not strong play, but meaningfully better than random — a useful middle rung.
- Results go into `benchmark_results` (§6), separate from the population's internal fitness. **A rising win-rate against these fixed opponents over time is the real evidence that evolution is working** — internal population fitness alone can't tell you that on its own.

---

## 6. Database Design

SQLite via plain `sqlite3` (stdlib, no ORM): a single file, zero setup, comfortably fast for the write/read volumes here (thousands of rows per run, not millions), and trivially portable to Postgres later if you ever want a multi-machine setup.

### `agents`

| Field | Type | Notes |
|---|---|---|
| agent_id | integer, PK | |
| parent1_id, parent2_id | FK → agents.agent_id, nullable | parent2 null for asexual reproduction; both null for the initial population |
| generation | integer | `max(parents' generation) + 1`; 0 for the initial population — an approximate lineage-depth metric, not a strict tick |
| birth_tick, death_tick | integer, death_tick nullable | |
| status | 'alive' / 'dead' | |
| death_cause | 'old_age' / 'culled', nullable | |
| nn_weights | JSON/blob | flattened weight vector |
| nn_architecture | JSON | layer sizes (fixed in MVP, mutable in the §3.4 extension) |
| lifespan, mutation_rate, crossover_rate | float/int | the gene values in §3.2 |
| games_played, wins, losses, draws | integer | running counters |
| fitness | float | recomputed each tick, §5 |
| games_since_last_reproduction | integer | drives §4.3 |
| offspring_count | integer | a lineage stat, free to compute |

### `games`

| Field | Type | Notes |
|---|---|---|
| game_id | integer, PK | |
| tick | integer | |
| player1_agent_id, player2_agent_id | FK → agents | |
| result | 'player1_win' / 'player2_win' / 'draw' | |
| num_moves | integer | |
| move_history | JSON | ordered list of column indices — enough to replay the whole game without a separate moves table |
| game_type | 'evolution' / 'human_vs_agent' / 'benchmark' | only 'evolution' games feed §5's fitness |

### `population_snapshots`

| Field | Type | Notes |
|---|---|---|
| snapshot_id | integer, PK | |
| tick | integer | |
| population_size | integer | |
| avg_fitness, max_fitness, min_fitness | float | |
| avg_lifespan, avg_mutation_rate | float | for watching gene drift over time, §9/§14 |
| best_agent_id | FK → agents | |

### `benchmark_results`

| Field | Type | Notes |
|---|---|---|
| benchmark_id | integer, PK | |
| tick | integer | |
| agent_id | FK → agents | |
| opponent_type | 'random' / 'heuristic' | |
| games_played, win_rate | integer, float | |

**Indices worth adding:** `agents.status`, `agents.parent1_id` / `parent2_id` (lineage lookups), `games.tick`, `games.player1_agent_id` / `player2_agent_id`. **A practical note:** commit games in a batch at the end of each tick rather than one commit per game — with hundreds of games a tick, per-game commits are where naive implementations lose most of their speed.

---

## 7. Software Architecture & Project Structure

```
connect4/
├── README.md
├── pyproject.toml               # uv-managed project metadata & dependencies
├── uv.lock
├── config.yaml                  # every tunable parameter from §10, in one place
├── src/
│   └── evoconnect4/
│       ├── config.py             # typed Config dataclass + config.yaml loader
│       ├── game/
│       │   ├── connect_four.py      # board state, legal moves, win detection -- pure logic, no I/O
│       │   ├── bots.py              # deterministic move-choosers: random mover, heuristic bot (§5)
│       │   └── match.py             # plays one full game between two move-choosing strategies
│       ├── agent/
│       │   ├── network.py           # feedforward NN: build from a flat weight vector, forward pass
│       │   ├── genome.py            # random init, encode/decode, mutate, crossover (§3)
│       │   └── agent.py             # wraps a genome + network + live stats
│       ├── evolution/
│       │   ├── population.py        # the live pool; runs one tick (§4.2)
│       │   ├── reproduction.py      # crossover + mutation operators
│       │   └── benchmarks.py        # random-mover & heuristic bots, benchmark runner (§5)
│       ├── storage/
│       │   ├── schema.py            # table definitions (§6), sqlite3 stdlib
│       │   └── repository.py        # agent/game CRUD, snapshot insert/read; benchmark_results CRUD deferred to Phase 6
│       ├── interface/
│       │   └── play_cli.py          # human vs. saved agent (§8)
│       ├── analytics/
│       │   └── plots.py             # charts from the DB (§9)
│       └── run_simulation.py        # entry point for a headless evolutionary run
├── tests/
│   ├── test_config.py
│   ├── test_connect_four.py
│   ├── test_bots.py
│   ├── test_match.py
│   ├── test_network.py
│   ├── test_genome.py
│   ├── test_agent.py
│   ├── test_schema.py
│   ├── test_repository.py
│   └── test_population.py
└── data/
    └── evoconnect4.db            # created at runtime
```

| Purpose | Recommended | Why |
|---|---|---|
| Package & dependency management | `uv` | Fast resolver/installer that can also provision the Python interpreter itself; manages `pyproject.toml` + `uv.lock` |
| Neural network math | `numpy` | Weights are just arrays; reshaping a flat genome vector into weight matrices is trivial, and nothing here needs autograd since nothing is trained by gradient |
| Game logic | Plain Python | Simple enough that a dependency would be overkill |
| Database | `sqlite3` (stdlib) | No new dependency |
| Config | `config.yaml` + a typed loader (`config.py`) | Tunables from §10 live in a human-editable file; the loader parses them into a typed dataclass so consuming code gets autocomplete/type-checking |
| Analytics | `matplotlib` (+ `pandas` optional) | Standard, simple, enough for the charts in §9 |
| Human CLI | `input()` / `print()` (stdlib) | Keeps the human interface as plain as the game itself |

**Why not an existing GA library:** libraries like DEAP or `neat-python` are excellent but built around generational (or NEAT-specific) assumptions that don't map cleanly onto the lifespan/reproduction-interval mechanics in §4. A custom, from-scratch loop is simple enough to hand-roll at this project's size, and it keeps every mechanic fully transparent and tunable. `neat-python` is worth a second look if you pursue full topology evolution later (§13).

---

## 8. Human-vs-Agent Interface

A terminal CLI (`play_cli.py`) that:

1. Loads a chosen agent from the database — by ID, or a convenience shortcut like "best currently alive" or "best ever" (dead agents keep their final stats, so this works even after that agent has passed).
2. Reconstructs its neural network from the stored genome.
3. Renders the board as text and alternates turns: prompts the human for a column (validating it's legal), computes the agent's move via the same relative-encoding forward pass used during evolution.
4. Reports the result at the end and logs the game with `game_type = 'human_vs_agent'`.

**By design, these games don't affect the agent's official `games_played`, `fitness`, or lifespan countdown** — same as benchmark games (§5), they're an exhibition/evaluation, not part of the evolutionary competition, so casual play never distorts the population's actual selective pressure. (If you'd rather make human games *count* — a form of interactive evolution — that's a one-line change to the logging step, just worth being a deliberate choice rather than a default.)

A simple graphical board (`pygame`, or even a tiny local web page) instead of ASCII text is a natural stretch addition — noted again in §13 — but adds nothing functionally the CLI doesn't already cover.

---

## 9. Analytics

With every agent, game, and snapshot in the database, a few plots (via `matplotlib`, reading from `population_snapshots` and `benchmark_results`) go a long way:

- **Population fitness over time** — avg / max / min fitness per tick. Expect noisy, possibly non-monotonic movement — that's normal for a co-evolving population (§5).
- **Baseline benchmark win-rate over time** — the "real" progress signal: win-rate vs. the random mover, and separately vs. the heuristic bot, per benchmark tick.
- **Population size over time** — should hover near the configured carrying capacity once culling kicks in.
- **Gene drift** — average `lifespan` and `mutation_rate` per tick. Does mutation strength settle somewhere sensible, or drift to an extreme (§14)? Does average lifespan creep toward its ceiling?
- **Lineage** *(nice-to-have)* — for a standout agent, walk `parent1_id`/`parent2_id` back through `agents` to sketch a family tree.

A Jupyter notebook or a couple of standalone scripts are both fine for the MVP; a small Streamlit dashboard is a reasonable stretch goal if you want it interactive.

---

## 10. Configuration Reference

| Parameter | Default | Description |
|---|---|---|
| `population_size` | 100 | Target carrying capacity of simultaneously-alive agents |
| `board_columns`, `board_rows` | 7, 6 | Connect Four board dimensions |
| `hidden_layer_sizes` | `[24]` | NN hidden layer widths (fixed at birth in the MVP) |
| `weight_init_std` | 0.5 | Std-dev of the Gaussian used to randomly seed initial weights |
| `lifespan_range` | `[30, 200]` | Min/max games an agent may live |
| `lifespan_mutation_scale` | 0.10 | Multiplicative std-dev applied to lifespan on reproduction |
| `mutation_rate_range` | `[0.01, 0.5]` | Bounds on an agent's own weight-mutation strength (σ) |
| `mutation_rate_tau` | 0.15 | Meta mutation rate for self-adapting σ (log-normal update, §3.2) |
| `crossover_rate_range` | `[0, 1]` | Bounds on an agent's own probability of sexual reproduction |
| `crossover_rate_mutation_std` | 0.05 | Additive Gaussian std-dev applied to crossover_rate on reproduction |
| `tournament_size` | 5 | Agents sampled when picking a second parent |
| `reproduction_interval_min` / `_max` | 8 / 25 | Bounds for the fitness→interval formula, §4.3 |
| `games_per_pair_per_tick` | 2 | Games per matched pair per tick (first-mover alternates) |
| `benchmark_every_n_ticks` | 10 | How often the current best agent faces the fixed baselines |
| `benchmark_games_per_opponent` | 20 | Games per baseline opponent at each benchmark point |
| `random_seed` | 42 | Single seed for reproducible runs |

---

## 11. Development Roadmap

| Phase | Goal | Done when |
|---|---|---|
| 0 — Scaffolding | Repo layout, config module, dependencies | Entry point runs end-to-end with stub logic |
| 1 — Game engine | Board, legal moves, win/draw detection, plus deterministic bots (random mover, heuristic bot) and a match runner pulled forward from Phase 6 as pure logic, with nothing structural (DB, population) attached | Unit tests cover all 4 win directions, draws, illegal moves |
| 2 — Agent & genome | NN forward pass, genome encode/decode, random init | Round-trip test: genome → network → identical weight vector back |
| 3 — Database | Schema (all 4 tables), full agent/game CRUD, snapshot insert/read; `benchmark_results` schema only, CRUD deferred to Phase 6 | Insert a fake agent + game, read both back correctly |
| 4 — Evolution core | Mutation, crossover, reproduction timing, death, population cap | 50-tick run on a small population shows plausible births/deaths, no runaway size |
| 4b — Evolution core updates | Parametrized (percentage-range + Beta-distribution-biased) culling with an optional lineage-aware immature-offspring tier, `Agent` lineage tracking (`parent1_id`/`parent2_id`), and a `games_per_pair_per_tick` config-wiring fix. See `plans/phase-4b-evolution-core-updates.md` | Cull-count distribution across repeated trials matches the configured range/bias; tier-2 (immature offspring) only activates when enabled and tier 1 is exhausted; `games_per_pair_per_tick` is honored |
| 5 — Full integration | Wire everything into `run_simulation.py`: CLI args (`--ticks`/`--seed`/`--db`), fresh-vs-resume run lifecycle, full config snapshotting (frozen + mutable-history, including a `simulation_id` assigned at fresh population creation for Phase 7's catalog to key on), RNG-state persistence for exact resume continuity. See `plans/phase-5-full-integration.md` | Multi-hundred-tick run completes with no crashes, DB fills in as expected; a paused-and-resumed run continues correctly; a mismatched frozen config refuses resume |
| 6 — Baseline benchmarking | Scheduled evaluation of the population's current-best agent against Phase 1's bots, writing to `benchmark_results`; `games` table extended to a unified, nullable-agent-id log so every game type (evolution/benchmark/human) stays fully replayable. See `plans/phase-6-baseline-benchmarking.md` | `benchmark_results` shows a visible trend over ticks |
| 7 — Analytics | Plotting scripts against the DB (§9), plus a cross-simulation catalog: a decoupled ETL step that rolls up each run's aggregate-only tables (population snapshots, benchmark results, frozen + initial config) into a shared `analytics.db`, keyed by `simulation_id`, for querying and comparing across runs without `ATTACH`-ing files by hand. See `plans/phase-7-analytics.md` | Charts in §9 generate from a completed run; running the catalog step against multiple run databases produces a queryable `analytics.db` where a single query can compare population/benchmark trends across runs by `simulation_id` |
| 8 — Human play | CLI loading a saved agent (by id, best-alive, or best-ever), board dimensions sourced from the database's frozen `simulation_config` rather than live `config.yaml`, a "play again?" session loop, and human-vs-agent games logged via Phase 6's already-generic `games` schema. See `plans/phase-8-human-play.md` | You can play a full game against the current best agent, start to finish |

---

## 12. Definition of Done (MVP)

- A headless simulation runs for several hundred ticks without crashing, with population size staying within the configured carrying capacity throughout.
- The database after such a run is a complete, queryable history — every agent (including dead ones) and every game, with lineage traceable back to the initial population via parent links.
- Baseline benchmark win-rate (at minimum, vs. the random mover) trends upward over the run — real evidence evolution is working, not just internal population noise (§5).
- A human can run the CLI, load the current best agent, and play a full, correctly-ruled game against it.

---

## 13. Possible Extensions

- **Structural mutation**: let `hidden_layer_sizes` itself mutate (grow/shrink a layer within bounds), so genomes evolve real structure, not just weights — closing the gap flagged in §3.4.
- **`neat-python`**: a mature off-the-shelf NEAT implementation (full topology evolution, speciation, historical markings) if you want to go further than simplified structural mutation.
- **Hall-of-fame opponents**: keep a roster of past strong agents (even after "death") that current agents occasionally face, so the population can't just get good at beating whoever's currently alive — a classic co-evolution fix.
- **Speciation / fitness sharing**: protect structurally novel genomes from being immediately out-competed, preserving diversity longer.
- **Fresh-blood injection**: periodically add a few brand-new random agents to guard against genetic bottlenecks in a fairly small population.
- **Parallelized game-play** (`multiprocessing`) if population size or tick count grows enough that wall-clock time matters.
- **A lightweight GUI** (`pygame`, or a tiny local web page) instead of the ASCII CLI board.
- **A different game entirely** — Othello/Reversi or grid-based Tron (§2's runners-up) — since the game engine sits behind an isolated interface, the agent/evolution/database layers wouldn't need to change.
- **Benchmark/human games counting toward fitness**: optionally let fixed-baseline (§5) or human-exhibition (§8) results feed into reproductive fitness, not just an agent's official record. Trade-off: benchmarks work today precisely because they don't co-evolve with the population — folding them in turns them into a selection target rather than an independent check, and their low game volume would need a weighting scheme to matter. Keep fitness counter-based if pursued, not recomputed by querying `games`.
- **Senescence (somatic mutation)**: live, in-play weight decay past a lifespan threshold, distinct from and never rejoining germline mutation — an offsetting cost for longevity, since `lifespan` is currently a purely dominant trait with no downside (the "pinning at its ceiling" risk in §14). Full design already worked out in §4.7. Not treated as its own roadmap phase since it's a small, self-contained addition to `Agent`'s live weights once the core loop is proven, not a full phase of work.

---

## 14. Risks & Things to Watch

- **Co-evolutionary blind spots**: fitness measured only against current population-mates can drift or cycle without genuine improvement (the "Red Queen" effect) — exactly why §5 recommends fixed-baseline benchmarking as the real progress signal.
- **Gene collapse or runaway**: `mutation_rate` could self-adapt toward its floor (the population stops exploring) — watch gene-value trends in `population_snapshots` (§9) to catch this early. `lifespan` pinning at its ceiling is the same class of risk, but has a planned structural mitigation rather than just monitoring — see §4.7's somatic-mutation/senescence design.
- **Diversity loss**: 100 agents is plenty for a toy project but can still bottleneck; fresh-blood injection or niching (§13) are the fixes if fitness plateaus early alongside low genome variance.
- **First-move advantage**: Connect Four's known first-player edge could bias fitness toward "who moved first" rather than "who played better" if left unchecked — mitigated in §4.6 by playing both orderings per matched pair.
- **Pure-Python performance ceiling**: fine at the scale in §10, but if population size or tick count grows substantially, batch DB commits and a vectorized `numpy` forward pass are the first things to optimize before anything structural.
