## 1. Config: four new mutable parameters

- [x] 1.1 Add `cull_fraction_range: list[float]`, `cull_fraction_beta_a: float`, `cull_fraction_beta_b: float`, and `cull_allow_immature_offspring: bool` fields to the `Config` dataclass in `src/evoconnect4/config.py` with defaults `[0.10, 0.50]`, `1.0`, `1.0`, and `False`; verify `load_config()` still succeeds after adding the corresponding keys to `config.yaml`

## 2. Agent: lineage fields in memory

- [x] 2.1 Add `parent1_id: int | None = None`, `parent2_id: int | None = None`, and `parent_avg_fitness: float = 0.0` as keyword parameters to `Agent.__init__`; update `Population._add_agent()` to pass `parent1_id`/`parent2_id` (already written to DB, now also set in memory) and compute `parent_avg_fitness` as the average of both parents' current `.fitness` for crossover children, the single parent's `.fitness` for clones, and `0.0` for the initial population; verify `test_agent_live_stats_default_to_zero` still passes with assertions for all three new defaults added
- [x] 2.2 Update `test_agent_live_stats_default_to_zero` in `tests/test_agent.py` to assert `agent.parent1_id is None` and `agent.parent2_id is None` by default; run the test suite and confirm no regressions

## 3. Population._play_pair: honor games_per_pair_per_tick

- [x] 3.1 Replace the `for first_mover in (1, -1)` loop in `Population._play_pair` with `for i in range(self.config.games_per_pair_per_tick): first_mover = 1 if i % 2 == 0 else -1`; verify existing `test_play_pair_records_two_games_with_move_history` still passes (it uses the default value of 2)
- [x] 3.2 Add a test `test_play_pair_honors_games_per_pair_per_tick` that sets `games_per_pair_per_tick=4`, calls `_play_pair`, and asserts exactly 4 games are recorded and the recorded `player1_agent_id` alternates between the two agents across the four games (verifying first-mover alternation)

## 4. Population._enforce_population_cap: variable Beta-distributed cull

- [x] 4.1 Rewrite `Population._enforce_population_cap` to: (a) return early if `len(alive) <= population_size`, (b) sample a fraction via `self.rng.beta(config.cull_fraction_beta_a, config.cull_fraction_beta_b)` and scale it into `cull_fraction_range`, (c) set `count = max(int(fraction * len(alive)), 1)`, (d) build `tier1` as mature agents sorted ascending by fitness and take `tier1[:count]` as initial candidates; verify the existing 50-tick DoD test `test_fifty_tick_run_shows_plausible_dynamics_and_no_runaway_size` still passes
- [x] 4.2 Add the optional tier-2 path: when `len(to_cull) < count` and `config.cull_allow_immature_offspring` is True, collect immature living agents not already in `to_cull`, sort them ascending by `agent.parent_avg_fitness` (no DB reads — uses the value cached on each `Agent` at birth), and append up to `count - len(to_cull)` from that sorted list; verify the existing cull test still passes
- [x] 4.3 Update `test_enforce_population_cap_culls_lowest_fitness_eligible_agent` in `tests/test_population.py` to use a fixed `cull_fraction_range=[1.0, 1.0]` (i.e. always cull 100% eligible) so the deterministic single-cull assertion remains valid; confirm the test still passes

## 5. Tests: culling specification coverage

- [x] 5.1 Add `test_cull_count_falls_within_configured_fraction_range`: run `_enforce_population_cap` 200 times on a population of 20 with capacity 10 and random Beta samples, collect the cull count each time, and assert all counts fall within `[max(1, floor(min_frac * 20)), floor(max_frac * 20)]`
- [x] 5.2 Add `test_cull_distribution_reflects_beta_shape`: run `_enforce_population_cap` 500 times with `a=b=5.0` (strongly bell-shaped, concentrated near midpoint of range) and `a=b=1.0` (uniform), and assert the mean fraction culled with `a=b=5.0` is closer to the midpoint of `cull_fraction_range` than the mean with `a=b=1.0`
- [x] 5.3 Add `test_tier2_never_activates_when_flag_off`: set `cull_allow_immature_offspring=False`, make the tier-1 pool contain zero agents (all agents are immature), call `_enforce_population_cap`, and assert the population is NOT reduced (tier-2 skipped, graceful under-fill accepted)
- [x] 5.4 Add `test_tier2_activates_after_tier1_exhausted`: set `cull_allow_immature_offspring=True`, create a scenario where tier-1 mature agents fill only part of the quota, assert that immature agents are culled to fill the remainder, and that the immature agents removed are those whose `parent_avg_fitness` is lowest (verify by constructing candidates with known differing `parent_avg_fitness` values)
- [x] 5.5 Add `test_at_least_one_culled_when_triggered_and_candidate_exists`: set `cull_fraction_range=[0.01, 0.01]` (tiny fraction, will round to 0, floor to minimum 1), trigger culling on a population one over capacity with one eligible mature agent, and assert exactly one agent is culled

## 6. Full test suite validation

- [x] 6.1 Run the full test suite (`pytest`) and confirm all tests pass, including the 50-tick DoD integration test; record any test that needed updating beyond what earlier tasks specified
