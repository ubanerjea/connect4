# EvoConnect4

Evolving neural-network agents to play Connect Four using a genetic algorithm — no backpropagation, no reinforcement-learning gradient, anywhere. An agent's neural network weights are a pure *phenotype*: expressed from its genome, used to play, and never directly adjusted. The only source of improvement is selection, mutation, and crossover acting on a population over time.

## How it works

- **The game**: standard Connect Four (7×6 board). A small headless rules engine plays out games with zero I/O; the same engine backs both evolution and human play.
- **The agent**: a small feedforward network (~1,200 weights, one hidden layer, `tanh` activation) reads the board and picks a column. Its genome also carries a lifespan, a self-adaptive mutation rate, and a crossover rate — all subject to evolution.
- **The population**: a *steady-state, continuously-running* pool, not synchronized generations. Each agent is born, plays, reproduces at fitness-driven intervals, and dies on its own schedule (when it reaches its own lifespan), all sharing one live pool. Population size is kept in check by culling the lowest-fitness agents when capacity is exceeded.
- **Fitness**: win rate within the population, cross-checked periodically against two fixed baseline opponents (a random mover and a simple heuristic bot) so genuine progress can be told apart from the population just getting better at beating itself.
- **Storage**: everything — every agent, every game, every birth and death, every population snapshot — is written to a SQLite database as it happens, so a run is a complete, queryable history afterward. Each run lives in its own database file.

The full design rationale lives in [`plans/evoconnect4_project_plan.md`](plans/evoconnect4_project_plan.md); phase-by-phase implementation history is in `openspec/changes/archive/`.

## Setup

```
uv sync
```

Tunable parameters (population size, mutation rates, board size, culling behavior, benchmark schedule, etc.) live in [`config.yaml`](config.yaml).

## Running a simulation

```
uv run python -m evoconnect4.run_simulation --ticks 500 --db data/mygame.db
```

- `--ticks` — how many ticks to run this invocation (default 500).
- `--db` — target database file (default: an auto-generated timestamped path under `data/`).
- `--seed` — RNG seed override (default: `config.yaml`'s `random_seed`).

### Resuming a run

The simulation doesn't have a "paused" state to sit in — each invocation just runs `--ticks` ticks and exits. But every tick's full state (population, tick count, exact RNG state) is committed to the database as it happens, so re-invoking against the same `--db` file picks up exactly where it left off, rather than starting over.

**Default — continue exactly as before:**

```
uv run python -m evoconnect4.run_simulation --ticks 500 --db data/mygame.db
```

Pointing `--db` at an existing database is automatically treated as a resume, not a fresh start. `--ticks` here means "how many *more* ticks to run" — if the population was at tick 500, this runs it to tick 1000. With no `--seed` given, the RNG stream continues bit-for-bit identically to how it would have if the process had never stopped.

**Branch onto a new random seed:**

```
uv run python -m evoconnect4.run_simulation --ticks 500 --db data/mygame.db --seed 99
```

Passing `--seed` at resume time deliberately diverges the run from that point forward, instead of continuing the original stream — useful for sampling a different outcome from the same population state.

**Changing other config between resumes:** most tunables in `config.yaml` (population size, mutation/crossover rates, tournament size, culling behavior, benchmark schedule, etc.) are read fresh at each resume, so editing them between invocations takes effect starting at the resume tick — the run's history keeps a record of exactly when each value changed. A few fields are locked in permanently at creation, though — board dimensions, network architecture (`hidden_layer_sizes`), and `weight_init_std` — because they're baked into every existing agent's stored weights. If `config.yaml` disagrees with the database on one of these, the resume is refused outright with a clear error rather than risking a corrupted population.

## Playing against an agent

```
uv run python -m evoconnect4.interface.play_cli --db data/mygame.db --agent best-alive
```

`--agent` accepts:
- `<id>` — a specific agent's exact id (alive or dead)
- `best-alive` — the fittest agent currently alive in that population
- `best-ever` — the fittest agent ever recorded, dead or alive

Once running:
1. Enter your name (or press Enter for "Anonymous Human").
2. Before each game, choose whether you move first.
3. The board is text-rendered — `X` is the agent, `O` is you, columns numbered 1–7 along the bottom. Enter a column number to drop your disc; invalid input just re-prompts.
4. Type `quit` at any move prompt (or `Ctrl+C`) to exit immediately — that game won't be saved.
5. After each game, choose whether to play again against the same agent.

Human games are logged for the record but never affect the agent's official fitness or evolutionary standing.

To find a specific agent's id rather than using `best-alive`/`best-ever`:

```
sqlite3 data/mygame.db "SELECT agent_id, fitness, status FROM agents ORDER BY fitness DESC LIMIT 10"
```

## Analytics

Charts from a single run:

```
uv run python -m evoconnect4.analytics.plots --db data/mygame.db --out-dir charts/
```

Generates population fitness, benchmark win-rate, population size, and gene-drift charts as PNGs.

Rolling up multiple runs into one queryable, comparable database:

```
uv run python -m evoconnect4.analytics.catalog --runs-dir data/ --analytics-db data/analytics.db
```

Safe to re-run any time — already-cataloged runs are skipped, and runs that have advanced further (via resume) are picked up incrementally.

## Development

```
uv run pytest
```
