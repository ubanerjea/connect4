# Phase 4b — Evolution Core Updates

*Parametrized culling, lineage tracking, and a config-wiring fix. Sits between Phase 4 (evolution core) and Phase 5 (full integration) in the roadmap — see `evoconnect4_project_plan.md` §11.*

This document is a self-contained brief for entering the OpenSpec propose/apply cycle. It assumes Phases 0-4 are already built and archived (game engine, agent/genome, storage, and the base evolution core with `Population`/`Agent`). No open questions remain — every decision below was explicitly resolved in the design conversation that produced this document.

## Why

Phase 4 built the simplest possible population-cap mechanism: whenever a reproduction event pushes the population over capacity, cull exactly one lowest-fitness eligible agent. That's a deliberately minimal placeholder, not the intended final behavior. This phase generalizes it into a fully parametrized, distribution-controlled mechanism, and fixes one small bug discovered while designing the run-lifecycle work in Phase 5.

## Scope

**In scope:**
1. Fix `games_per_pair_per_tick` — currently hardcoded in `population.py`'s `_play_pair` (`for first_mover in (1, -1)`), ignoring `config.games_per_pair_per_tick` entirely. Wire the actual config value in.
2. Add `Agent.parent1_id` / `Agent.parent2_id` as in-memory fields (mirroring the existing `agent_id`/`generation` additions from Phase 4) — needed here for lineage-aware culling, and reused as-is by Phase 5's `Population.load()`.
3. Redesign `Population._enforce_population_cap()` to cull a *variable count* of agents per triggering event, drawn from a configurable percentage range with a configurable distributional bias, instead of always exactly one.
4. Add an optional second tier to the cull-candidate pool: immature (not-yet-eligible) living agents whose parent(s) rank low in fitness, used only to fill any remaining quota after the mature-agent pool is exhausted.
5. Four new config parameters (see below), all classified as **mutable/live** for Phase 5's config-history mechanism — they're re-read fresh from `Config` on every use, never baked into stored per-agent data.

**Out of scope:**
- *When* culling is checked — unchanged from Phase 4: after every individual reproduction event, not once per tick.
- The mature-eligibility floor itself — unchanged: `games_played >= reproduction_interval_min`.
- Config snapshotting / the frozen-vs-mutable storage split — that's Phase 5's mechanism. This phase only needs to flag its new config keys as mutable for Phase 5 to pick up; it doesn't build the persistence itself.

## New config parameters

| Parameter | Default | Description |
|---|---|---|
| `cull_fraction_range` | `[0.10, 0.50]` | Min/max fraction of the current alive population culled per triggering event |
| `cull_fraction_beta_a` | `1.0` | Beta-distribution alpha shape parameter for sampling within the range |
| `cull_fraction_beta_b` | `1.0` | Beta-distribution beta shape parameter (`a=b=1.0` → uniform; no built-in skew by default) |
| `cull_allow_immature_offspring` | `false` | When true, allows the immature-offspring tier to fill any cull quota remaining after the mature-agent pool is exhausted |

All four are **mutable/live** (Phase 5's allowlist) — none are stored per-agent, so changing them at a later resume point takes effect immediately for future culling events.

## Design: the culling algorithm

Replaces `Population._enforce_population_cap()` in full.

```
IF len(alive) <= population_size: return

# 1. How many to cull -- percentage range + Beta-distribution bias
t = rng.beta(cull_fraction_beta_a, cull_fraction_beta_b)          # in [0, 1]
fraction = cull_fraction_range[0] + t * (cull_fraction_range[1] - cull_fraction_range[0])
count = int(fraction * len(alive))                                 # rounded down
count = max(count, 1)                                              # always at least 1 when triggered

# 2. Tier 1: mature agents, lowest fitness first (unchanged eligibility rule)
tier1 = sorted(
    [a for a in alive if a.games_played >= reproduction_interval_min],
    key=lambda a: a.fitness,
)
to_cull = tier1[:count]

# 3. Tier 2 (optional): immature living agents whose parent(s) rank low in
#    fitness -- only used to fill whatever's left of the quota, and only
#    when the config toggle is on
IF len(to_cull) < count AND cull_allow_immature_offspring:
    tier2_candidates = [a for a in alive
                         if a.games_played < reproduction_interval_min
                         and a not in to_cull]

    FUNCTION parent_fitness_rank(agent):
        # A parent may be alive or dead -- repo.get_agent() returns either
        # (no status filter), so a dead low-fitness parent's record still
        # counts. Crossover children: average of both parents' fitness.
        # Cloned children: the single parent's fitness.
        IF agent.parent2_id is not None:
            RETURN (fitness(agent.parent1_id) + fitness(agent.parent2_id)) / 2
        ELSE:
            RETURN fitness(agent.parent1_id)

    tier2_sorted = sorted(tier2_candidates, key=parent_fitness_rank)
    to_cull += tier2_sorted[: count - len(to_cull)]

# 4. Cull everything selected (fewer than `count` if both tiers combined
#    don't have enough candidates -- graceful under-fill, same tolerance
#    Phase 4 already had for "no eligible agents yet")
FOR agent in to_cull:
    kill(agent, cause="culled")
```

*(Pseudocode — an outline of the algorithm, not implementation, same convention as plan §4.2.)*

## `games_per_pair_per_tick` fix

Replace the hardcoded `for first_mover in (1, -1)` in `_play_pair` with a loop of `config.games_per_pair_per_tick` iterations, alternating first-mover strictly (`+1` for even iteration index, `-1` for odd) — preserves today's behavior exactly when the value is `2` (the default), and generalizes cleanly to any other value.

## `Agent.parent1_id` / `parent2_id`

Add as constructor parameters (`agent_id: int | None = None`-style, defaulting to `None`), set at `Population._add_agent()` time from the same `parent1_id`/`parent2_id` values already passed to `repo.insert_agent()` — no new data, just also attaching it to the in-memory `Agent` object rather than only writing it to the DB row.

## Dependencies

Builds directly on Phase 4's `Population`/`Agent`/`Repository`. No new external dependencies — Beta-distribution sampling is `numpy.random.Generator.beta`, already available via the existing `self.rng`.

## Definition of done

- A unit test running many repeated triggering events confirms the culled fraction falls within `cull_fraction_range` and, over enough trials, its distribution reflects the configured Beta shape (e.g. visibly more concentrated near the range's midpoint when `a=b=2.0` versus flat when `a=b=1.0`).
- A unit test confirms tier 2 never activates when `cull_allow_immature_offspring` is `false`, even if tier 1 can't fill the quota (population size may temporarily exceed capacity in this case — an accepted, existing-style tolerance, same as Phase 4's "no eligible agents yet" case).
- A unit test confirms tier 2 activates only once tier 1 is exhausted, and ranks candidates by average-of-both-parents fitness for crossover children, single-parent fitness for clones — including a case where the ranked parent is already dead.
- A unit test confirms at least 1 agent is always culled when the trigger fires and at least one eligible candidate (tier 1 or tier 2) exists.
- A unit test confirms `games_per_pair_per_tick` is honored — e.g. set to `4` and confirm exactly 4 games are recorded per pair per tick, alternating first-mover.
- Full existing test suite continues to pass.

## Known limitations / deliberate trade-offs

- Culling up to 50% of the population in a single event (the default range's high end) produces a **boom-bust** population-size dynamic rather than Phase 4's smooth one-in-one-out equilibrium. This is an intentional, explicitly-chosen behavior change — not a bug — and will be visible in Phase 7's population-size-over-time charts. Tune `cull_fraction_range` down, or `cull_allow_immature_offspring` off, for a gentler dynamic if desired.
- The trigger point itself (checked after every individual reproduction event) is unchanged from Phase 4. A single triggering event can now remove a large fraction of the population in one pass, but the *frequency* of checks hasn't changed.
