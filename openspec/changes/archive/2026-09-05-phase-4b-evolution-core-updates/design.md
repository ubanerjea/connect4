## Context

Three independent changes land in the same phase because they share a dependency surface: the `Agent` lineage fields are needed by the tier-2 culling path, and both sit inside `Population`/`Agent` which the `games_per_pair_per_tick` fix also touches. All four new config keys are mutable/live — Phase 5 will need them on its allowlist but does not build the config-snapshotting mechanism here.

Current state of the affected code:
- `Agent.__init__` carries `agent_id` and `generation` but not `parent1_id`/`parent2_id`, even though those values are already written to the DB by `_add_agent`.
- `_play_pair` loops over the literal tuple `(1, -1)`, ignoring `config.games_per_pair_per_tick`.
- `_enforce_population_cap` always culls exactly one mature agent or does nothing.

## Goals / Non-Goals

**Goals:**
- Make `Agent` carry its own lineage in memory so callers (e.g., tier-2 culling, and Phase 5's `Population.load()`) don't need a DB round-trip.
- Replace the single-agent cull with a Beta-distributed variable-count cull.
- Make the immature-offspring tier opt-in so default behavior (flag off) is conservative.
- Honor `games_per_pair_per_tick` for correct behavior at any configured value.

**Non-Goals:**
- Config snapshotting / mutable-vs-frozen split — Phase 5.
- `Population.load()` / resume lifecycle — Phase 5.
- Any change to when culling is triggered (still: after every individual reproduction event).
- Changing what "mature" means (still: `games_played >= reproduction_interval_min`).

## Decisions

**D1: Beta distribution for cull fraction sampling**
Use `numpy.random.Generator.beta(a, b)` (already available via `self.rng`) to sample a value in [0, 1], then linearly scale it into `cull_fraction_range`. Defaults `a=b=1.0` give uniform sampling with no built-in skew. This is tunable without code changes by adjusting the shape parameters in config.

Alternative considered: fixed random uniform sampling. Rejected because the plan explicitly calls for a configurable distributional bias; a Beta gives the full family of U/bell/skewed shapes in one parameter pair.

**D2: Minimum cull of 1 when triggered**
`count = max(int(fraction * len(alive)), 1)`. At small population sizes the fractional result can round to zero; a hard floor of 1 ensures the cap is enforced whenever the trigger fires and any eligible candidate exists.

**D3: Tier-2 ranking uses parent fitness cached on the child at birth**
Rather than reading from the DB at cull time, `Agent` carries a `parent_avg_fitness: float` field set in `_add_agent` to the average of both parents' current fitness (crossover) or the single parent's current fitness (clone), with `0.0` for the initial population. The tier-2 sort uses `agent.parent_avg_fitness` directly — no DB reads at cull time, regardless of population size.

Trade-off: this captures parent fitness at birth, not the parent's final recorded value. If a parent's fitness changes substantially after a child is born, the cached rank will drift from a live-lookup rank. In practice, parent fitness is most informative at birth (it's the signal that drove reproduction timing), so birth-time caching is the right snapshot to use, not a compromise forced by the performance constraint.

Alternative considered: `repo.get_agent()` per candidate at cull time. Rejected because it requires O(immature_count × 2) DB reads per culling event and the trade-off is not worth it — birth-time fitness is the more meaningful signal anyway.

**D4: `Agent.parent1_id`/`parent2_id` as plain constructor parameters**
Match the existing pattern for `agent_id` and `generation`: optional keyword parameters defaulting to `None`, set at construction time by `_add_agent`. The DB already stores these values; this just propagates them to the in-memory object so downstream code doesn't need a DB lookup.

**D5: `_play_pair` loop uses iteration index for first-mover parity**
`for i in range(config.games_per_pair_per_tick): first_mover = 1 if i % 2 == 0 else -1`. When the config value is 2 (the default), this is exactly equivalent to the current `for first_mover in (1, -1)` behavior.

## Risks / Trade-offs

- **Boom-bust population dynamics**: With default `cull_fraction_range=[0.10, 0.50]`, a single triggering event can remove up to half the population at once. This is intentional per the plan, but will be visible in Phase 7 charts. Tuning the range down or using skewed Beta parameters mitigates it.
  
- **Graceful under-fill**: If neither tier provides enough candidates to reach `count`, the system culls only what's available. This reuses the tolerance already present in Phase 4's "no eligible agents yet" case and is documented in the spec.
