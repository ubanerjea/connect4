# EvoConnect4

EvoConnect4 evolves neural-network agents to play Connect Four using a genetic
algorithm — no backpropagation, no reinforcement-learning gradient, anywhere. An
agent's network weights are a pure phenotype, expressed from its genome and used to
play, but never directly adjusted; the only source of improvement is selection,
mutation, and crossover acting on a steady-state, continuously-running population over
time.

Every run is a complete, queryable SQLite history (see `data/DB_SCHEMA.MD`), and the
project also supports benchmarking evolved agents against fixed baseline bots and
letting a human play against any saved agent from the terminal. See `README.md` for
setup, running, playing, and managing runs.

## Rules for agents

1. **Run the relevant test suite before considering a change done.** After editing
   code, run `uv run pytest` (or a targeted subset of test files if the change is
   narrow and you want a fast signal first) and make sure it passes — don't report
   work as finished on the strength of it "looking right."
2. **Keep `data/DB_SCHEMA.MD` in sync with the database.** Any change to the schema
   itself (a new table, column, or index) or to how it's managed, migrated, or consumed
   (e.g. what applies pending schema changes to an existing file, or how the analytics
   catalog rolls runs up) must be reflected there as part of the same change.
