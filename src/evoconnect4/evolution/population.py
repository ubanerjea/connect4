"""Population: the live pool, running one tick (plan Sec4.2).

Wires together the game engine (Phase 1), agents/genome (Phase 2), and
storage (Phase 3). Phase 10 adds three-track adaptive fitness, Hall of Fame
challenges and maintenance.
"""

from __future__ import annotations

import functools

import numpy as np

from evoconnect4.agent.agent import Agent
from evoconnect4.agent.genome import Genome, crossover, decode, encode, mutate, random_genome
from evoconnect4.config import Config
from evoconnect4.game.bots import get_heuristic_bot, random_mover
from evoconnect4.game.match import play_match
from evoconnect4.storage.repository import Repository

_BASELINE_OPPONENTS = ((random_mover, "random"),)


def reproduction_interval(fitness: float, config: Config) -> float:
    lo, hi = config.reproduction_interval_min, config.reproduction_interval_max
    interval = hi - fitness * (hi - lo)
    return min(max(interval, lo), hi)


def _compute_adaptive_betas(
    rolling_wr: float,
    *,
    beta_h_max: float,
    beta_h_min: float,
    adapt_low: float,
    adapt_high: float,
    hof_weight_max: float,
    hof_has_members: bool,
) -> tuple[float, float, float]:
    denom = adapt_high - adapt_low
    t = 0.0 if denom <= 0 else max(0.0, min(1.0, (rolling_wr - adapt_low) / denom))
    beta_h = beta_h_max - t * (beta_h_max - beta_h_min)
    beta_hof = (t * hof_weight_max) if hof_has_members else 0.0
    beta_peer = 1.0 - beta_h - beta_hof
    return beta_peer, beta_h, beta_hof


class Population:
    def __init__(self, config: Config, repo: Repository, rng: np.random.Generator | None = None) -> None:
        self.config = config
        self.repo = repo
        self.rng = rng if rng is not None else np.random.default_rng(config.random_seed)
        self.tick = 0
        self.alive: list[Agent] = []
        self._hof_agents: list[Agent] = []

    def initialize(self) -> None:
        for _ in range(self.config.population_size):
            genome = random_genome(self.config, rng=self.rng)
            self._add_agent(genome, parent1_id=None, parent2_id=None, generation=0)
        self.repo.commit()

    @classmethod
    def load(cls, config: Config, repo: Repository) -> tuple["Population", str]:
        """Reconstruct a live population from storage -- the resume counterpart to initialize().

        Returns the population and the persisted RNG state string; the caller
        decides whether to restore it exactly or branch to a new seed (plan
        Sec5's resume semantics), so it is not applied here.
        """
        population = cls(config, repo)
        for record in repo.list_agents(status="alive"):
            genome = decode(
                {
                    "weights": record["nn_weights"],
                    "hidden_layer_sizes": record["nn_architecture"],
                    "lifespan": record["lifespan"],
                    "mutation_rate": record["mutation_rate"],
                    "crossover_rate": record["crossover_rate"],
                }
            )
            agent = Agent(
                genome,
                config.board_columns,
                config.board_rows,
                agent_id=record["agent_id"],
                generation=record["generation"],
                parent1_id=record["parent1_id"],
                parent2_id=record["parent2_id"],
                parent_avg_fitness=record["parent_avg_fitness"],
            )
            agent.games_played = record["games_played"]
            agent.wins = record["wins"]
            agent.losses = record["losses"]
            agent.draws = record["draws"]
            agent.fitness = record["fitness"]
            agent.games_since_last_reproduction = record["games_since_last_reproduction"]
            agent.peer_wins = record["peer_wins"]
            agent.peer_draws = record["peer_draws"]
            agent.peer_games_played = record["peer_games_played"]
            agent.heuristic_wins = record["heuristic_wins"]
            agent.heuristic_draws = record["heuristic_draws"]
            agent.heuristic_games_played = record["heuristic_games_played"]
            agent.heuristic_survival_credit = record["heuristic_survival_credit"]
            agent.hof_wins = record.get("hof_wins", 0)
            agent.hof_draws = record.get("hof_draws", 0)
            agent.hof_games_played = record.get("hof_games_played", 0)
            agent.hof_survival_credit = record.get("hof_survival_credit", 0.0)
            population.alive.append(agent)

        # Reconstruct active HoF members as Agent objects ready for per-tick sampling.
        for hof_record in repo.list_hof_agents(status="active"):
            agent_record = repo.get_agent(hof_record["agent_id"])
            if agent_record is None:
                continue
            genome = decode(
                {
                    "weights": agent_record["nn_weights"],
                    "hidden_layer_sizes": agent_record["nn_architecture"],
                    "lifespan": agent_record["lifespan"],
                    "mutation_rate": agent_record["mutation_rate"],
                    "crossover_rate": agent_record["crossover_rate"],
                }
            )
            hof_agent = Agent(
                genome,
                config.board_columns,
                config.board_rows,
                agent_id=agent_record["agent_id"],
            )
            hof_agent._hof_record_id = hof_record["id"]
            population._hof_agents.append(hof_agent)

        state = repo.get_simulation_state()
        population.tick = state["current_tick"]
        return population, state["rng_state"]

    def run_tick(self) -> None:
        self.tick += 1

        for agent_a, agent_b in self._pair_alive():
            self._play_pair(agent_a, agent_b)

        self._run_heuristic_challenges()

        self._run_hof_challenges()

        self._recompute_fitness()

        for agent in list(self.alive):
            if agent not in self.alive:
                continue
            interval = reproduction_interval(agent.fitness, self.config)
            if agent.games_since_last_reproduction >= interval:
                self._reproduce(agent)
            if agent in self.alive and agent.games_played >= agent.genome.lifespan:
                self._kill(agent, cause="old_age")

        self._run_benchmark()

        self._run_hof_maintenance()

        self._write_snapshot()
        self.repo.commit()

    # -- internals -------------------------------------------------------

    def _add_agent(
        self,
        genome: Genome,
        *,
        parent1_id: int | None,
        parent2_id: int | None,
        generation: int,
        parent_avg_fitness: float = 0.0,
    ) -> Agent:
        encoded = encode(genome)
        agent_id = self.repo.insert_agent(
            parent1_id=parent1_id,
            parent2_id=parent2_id,
            generation=generation,
            birth_tick=self.tick,
            status="alive",
            nn_weights=encoded["weights"],
            nn_architecture=encoded["hidden_layer_sizes"],
            lifespan=genome.lifespan,
            mutation_rate=genome.mutation_rate,
            crossover_rate=genome.crossover_rate,
            parent_avg_fitness=parent_avg_fitness,
        )
        agent = Agent(
            genome,
            self.config.board_columns,
            self.config.board_rows,
            agent_id=agent_id,
            generation=generation,
            parent1_id=parent1_id,
            parent2_id=parent2_id,
            parent_avg_fitness=parent_avg_fitness,
        )
        self.alive.append(agent)
        return agent

    def _pair_alive(self) -> list[tuple[Agent, Agent]]:
        shuffled = list(self.alive)
        self.rng.shuffle(shuffled)
        pairs = []
        i = 0
        while i + 1 < len(shuffled):
            pairs.append((shuffled[i], shuffled[i + 1]))
            i += 2
        return pairs

    def _play_pair(self, agent_a: Agent, agent_b: Agent) -> None:
        for i in range(self.config.games_per_pair_per_tick):
            first_mover = 1 if i % 2 == 0 else -1
            result = play_match(agent_a.choose_move, agent_b.choose_move, first_mover=first_mover)
            self._record_game(agent_a, agent_b, result)

    def _record_game(self, agent_a: Agent, agent_b: Agent, result) -> None:
        if result.winner == 1:
            db_result = "player1_win"
            agent_a.wins += 1
            agent_a.peer_wins += 1
            agent_b.losses += 1
        elif result.winner == -1:
            db_result = "player2_win"
            agent_a.losses += 1
            agent_b.wins += 1
            agent_b.peer_wins += 1
        else:
            db_result = "draw"
            agent_a.draws += 1
            agent_a.peer_draws += 1
            agent_b.draws += 1
            agent_b.peer_draws += 1

        agent_a.games_played += 1
        agent_a.peer_games_played += 1
        agent_b.games_played += 1
        agent_b.peer_games_played += 1
        agent_a.games_since_last_reproduction += 1
        agent_b.games_since_last_reproduction += 1

        self.repo.insert_game(
            tick=self.tick,
            player1_agent_id=agent_a.agent_id,
            player2_agent_id=agent_b.agent_id,
            result=db_result,
            num_moves=result.num_moves,
            move_history=result.move_history,
            game_type="evolution",
        )
        self._persist_stats(agent_a)
        self._persist_stats(agent_b)

    def _persist_stats(self, agent: Agent) -> None:
        self.repo.update_agent_stats(
            agent.agent_id,
            games_played=agent.games_played,
            wins=agent.wins,
            losses=agent.losses,
            draws=agent.draws,
            fitness=agent.fitness,
            games_since_last_reproduction=agent.games_since_last_reproduction,
            peer_wins=agent.peer_wins,
            peer_draws=agent.peer_draws,
            peer_games_played=agent.peer_games_played,
            heuristic_wins=agent.heuristic_wins,
            heuristic_draws=agent.heuristic_draws,
            heuristic_games_played=agent.heuristic_games_played,
            heuristic_survival_credit=agent.heuristic_survival_credit,
            hof_wins=agent.hof_wins,
            hof_draws=agent.hof_draws,
            hof_games_played=agent.hof_games_played,
            hof_survival_credit=agent.hof_survival_credit,
        )

    def _recompute_fitness(self) -> None:
        rolling_wr = self.repo.get_rolling_heuristic_win_rate(
            window=self.config.heuristic_weight_adapt_window
        )
        if rolling_wr is None:
            rolling_wr = 0.0

        beta_peer, beta_h, beta_hof = _compute_adaptive_betas(
            rolling_wr,
            beta_h_max=self.config.heuristic_fitness_weight_max,
            beta_h_min=self.config.heuristic_fitness_weight_min,
            adapt_low=self.config.heuristic_weight_adapt_low,
            adapt_high=self.config.heuristic_weight_adapt_high,
            hof_weight_max=self.config.hof_fitness_weight_max if self.config.hof_enabled else 0.0,
            hof_has_members=bool(self._hof_agents),
        )

        for agent in self.alive:
            peer_fitness = (
                (agent.peer_wins + 0.5 * agent.peer_draws) / agent.peer_games_played
                if agent.peer_games_played > 0 else 0.0
            )
            heuristic_fitness = (
                (agent.heuristic_wins + 0.5 * agent.heuristic_draws + agent.heuristic_survival_credit)
                / agent.heuristic_games_played
                if agent.heuristic_games_played > 0 else 0.0
            )
            hof_fitness = (
                (agent.hof_wins + 0.5 * agent.hof_draws + agent.hof_survival_credit)
                / agent.hof_games_played
                if agent.hof_games_played > 0 else 0.0
            )
            agent.fitness = beta_peer * peer_fitness + beta_h * heuristic_fitness + beta_hof * hof_fitness
            self._persist_stats(agent)

    def _tournament_select(self, exclude: Agent) -> Agent | None:
        candidates = [a for a in self.alive if a is not exclude]
        k = min(self.config.tournament_size, len(candidates))
        if k == 0:
            return None
        indices = self.rng.choice(len(candidates), size=k, replace=False)
        sample = [candidates[i] for i in indices]
        return max(sample, key=lambda a: a.fitness)

    def _reproduce(self, parent: Agent) -> None:
        partner = None
        if self.rng.random() < parent.genome.crossover_rate:
            partner = self._tournament_select(exclude=parent)

        if partner is not None:
            child_genome = crossover(parent.genome, partner.genome, rng=self.rng)
            child_genome = mutate(child_genome, self.config, rng=self.rng)
            parent2_id = partner.agent_id
            generation = max(parent.generation, partner.generation) + 1
            parent_avg_fitness = (parent.fitness + partner.fitness) / 2.0
        else:
            child_genome = mutate(parent.genome, self.config, rng=self.rng)
            parent2_id = None
            generation = parent.generation + 1
            parent_avg_fitness = parent.fitness

        self._add_agent(
            child_genome,
            parent1_id=parent.agent_id,
            parent2_id=parent2_id,
            generation=generation,
            parent_avg_fitness=parent_avg_fitness,
        )

        parent.games_since_last_reproduction = 0
        self._persist_stats(parent)

        self._enforce_population_cap()

    def _enforce_population_cap(self) -> None:
        if len(self.alive) <= self.config.population_size:
            return

        lo, hi = self.config.cull_fraction_range
        t = self.rng.beta(self.config.cull_fraction_beta_a, self.config.cull_fraction_beta_b)
        fraction = lo + t * (hi - lo)
        count = max(int(fraction * len(self.alive)), 1)

        tier1 = sorted(
            [a for a in self.alive if a.games_played >= self.config.reproduction_interval_min],
            key=lambda a: a.fitness,
        )
        to_cull = tier1[:count]

        if len(to_cull) < count and self.config.cull_allow_immature_offspring:
            tier2 = sorted(
                [a for a in self.alive if a.games_played < self.config.reproduction_interval_min and a not in to_cull],
                key=lambda a: a.parent_avg_fitness,
            )
            to_cull = to_cull + tier2[: count - len(to_cull)]

        for agent in to_cull:
            self._kill(agent, cause="culled")

    def _kill(self, agent: Agent, *, cause: str) -> None:
        self.repo.mark_agent_dead(agent.agent_id, death_tick=self.tick, death_cause=cause)
        self.alive.remove(agent)

    def _run_heuristic_challenges(self) -> None:
        n = self.config.heuristic_games_per_agent_per_tick
        if n <= 0 or not self.alive:
            return

        heuristic_fn = get_heuristic_bot(self.config.heuristic_bot_level)
        bound_heuristic = functools.partial(heuristic_fn, rng=self.rng)
        board_cells = self.config.board_columns * self.config.board_rows
        alpha = self.config.heuristic_survival_alpha

        for agent in self.alive:
            for i in range(n):
                first_mover = 1 if i % 2 == 0 else -1
                result = play_match(agent.choose_move, bound_heuristic, first_mover=first_mover)

                if result.winner == 1:
                    db_result = "player1_win"
                    agent.heuristic_wins += 1
                    agent.wins += 1
                elif result.winner == -1:
                    db_result = "player2_win"
                    agent.heuristic_survival_credit += alpha * result.num_moves / board_cells
                    agent.losses += 1
                else:
                    db_result = "draw"
                    agent.heuristic_draws += 1
                    agent.draws += 1

                agent.heuristic_games_played += 1
                agent.games_played += 1
                agent.games_since_last_reproduction += 1

                self.repo.insert_game(
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

    def _run_hof_challenges(self) -> None:
        if not self.config.hof_enabled:
            return
        n = self.config.hof_games_per_agent_per_tick
        if n <= 0 or not self.alive or not self._hof_agents:
            return

        board_cells = self.config.board_columns * self.config.board_rows
        alpha = self.config.heuristic_survival_alpha

        for agent in self.alive:
            for i in range(n):
                first_mover = 1 if i % 2 == 0 else -1
                hof_member = self._hof_agents[int(self.rng.integers(len(self._hof_agents)))]
                result = play_match(agent.choose_move, hof_member.choose_move, first_mover=first_mover)

                if result.winner == 1:
                    db_result = "player1_win"
                    agent.hof_wins += 1
                    agent.wins += 1
                elif result.winner == -1:
                    db_result = "player2_win"
                    agent.hof_survival_credit += alpha * result.num_moves / board_cells
                    agent.losses += 1
                else:
                    db_result = "draw"
                    agent.hof_draws += 1
                    agent.draws += 1

                agent.hof_games_played += 1
                agent.games_played += 1
                agent.games_since_last_reproduction += 1

                self.repo.insert_game(
                    tick=self.tick,
                    player1_agent_id=agent.agent_id,
                    player2_agent_id=hof_member.agent_id,
                    result=db_result,
                    num_moves=result.num_moves,
                    move_history=result.move_history,
                    game_type="hof_challenge",
                )
                self._persist_stats(agent)

    def _run_hof_maintenance(self) -> None:
        if not self.config.hof_enabled:
            return
        if self.tick % self.config.hof_maintenance_every_n_ticks != 0:
            return
        if not self.alive:
            return

        heuristic_fn = get_heuristic_bot(self.config.heuristic_bot_level)
        bound_heuristic = functools.partial(heuristic_fn, rng=self.rng)
        active_hof_records = self.repo.list_hof_agents(status="active")

        # Step 1: Re-evaluate each existing member vs heuristic bot.
        for hof_record in active_hof_records:
            member = self._find_hof_agent(hof_record["id"])
            if member is None:
                continue
            wins = draws = 0
            n = self.config.hof_maintenance_heuristic_games
            for i in range(n):
                first_mover = 1 if i % 2 == 0 else -1
                result = play_match(member.choose_move, bound_heuristic, first_mover=first_mover)
                if result.winner == 1:
                    wins += 1
                    db_result = "player1_win"
                elif result.winner == -1:
                    db_result = "player2_win"
                else:
                    draws += 1
                    db_result = "draw"
                self.repo.insert_game(
                    tick=self.tick,
                    player1_agent_id=member.agent_id,
                    player2_agent_id=None,
                    result=db_result,
                    num_moves=result.num_moves,
                    move_history=result.move_history,
                    game_type="hof_maintenance_heuristic",
                    opponent_label="heuristic",
                )
            member_wr = (wins + 0.5 * draws) / n
            self.repo.update_hof_heuristic_win_rate(hof_record["id"], member_wr)
            hof_record["heuristic_win_rate"] = member_wr

        # Step 2: Intra-HoF pairing.
        if len(active_hof_records) >= 2:
            n_pairs = self.config.hof_maintenance_peer_games
            indices = list(range(len(active_hof_records)))
            self.rng.shuffle(indices)
            win_counts: dict[int, list] = {r["id"]: [0, 0, 0] for r in active_hof_records}  # wins, draws, games

            for idx in range(0, len(indices) - 1, 2):
                ra = active_hof_records[indices[idx]]
                rb = active_hof_records[indices[idx + 1]]
                ma = self._find_hof_agent(ra["id"])
                mb = self._find_hof_agent(rb["id"])
                if ma is None or mb is None:
                    continue
                for i in range(n_pairs):
                    first_mover = 1 if i % 2 == 0 else -1
                    result = play_match(ma.choose_move, mb.choose_move, first_mover=first_mover)
                    if result.winner == 1:
                        db_result = "player1_win"
                        win_counts[ra["id"]][0] += 1
                    elif result.winner == -1:
                        db_result = "player2_win"
                        win_counts[rb["id"]][0] += 1
                    else:
                        db_result = "draw"
                        win_counts[ra["id"]][1] += 1
                        win_counts[rb["id"]][1] += 1
                    win_counts[ra["id"]][2] += 1
                    win_counts[rb["id"]][2] += 1
                    self.repo.insert_game(
                        tick=self.tick,
                        player1_agent_id=ma.agent_id,
                        player2_agent_id=mb.agent_id,
                        result=db_result,
                        num_moves=result.num_moves,
                        move_history=result.move_history,
                        game_type="hof_maintenance_peer",
                    )

            for hof_record in active_hof_records:
                w, d, g = win_counts[hof_record["id"]]
                internal = (w + 0.5 * d) / g if g > 0 else 0.0
                combined = 0.5 * hof_record["heuristic_win_rate"] + 0.5 * internal
                self.repo.update_hof_scores(hof_record["id"], internal_score=internal, combined_score=combined)
                hof_record["combined_score"] = combined

        # Step 3: Evaluate candidate (current best-alive by fitness).
        candidate = max(self.alive, key=lambda a: a.fitness)
        c_wins = c_draws = 0
        n = self.config.hof_maintenance_heuristic_games
        for i in range(n):
            first_mover = 1 if i % 2 == 0 else -1
            result = play_match(candidate.choose_move, bound_heuristic, first_mover=first_mover)
            if result.winner == 1:
                c_wins += 1
                db_result = "player1_win"
            elif result.winner == -1:
                db_result = "player2_win"
            else:
                c_draws += 1
                db_result = "draw"
            self.repo.insert_game(
                tick=self.tick,
                player1_agent_id=candidate.agent_id,
                player2_agent_id=None,
                result=db_result,
                num_moves=result.num_moves,
                move_history=result.move_history,
                game_type="hof_maintenance_heuristic",
                opponent_label="heuristic",
            )
        candidate_wr = (c_wins + 0.5 * c_draws) / n

        # Step 4: Entry / eviction decision.
        threshold = self.config.hof_entry_heuristic_threshold
        if candidate_wr < threshold:
            return

        active_agent_ids = {r["agent_id"] for r in active_hof_records}
        if candidate.agent_id in active_agent_ids:
            return

        if len(active_hof_records) < self.config.hof_max_size:
            hof_id = self.repo.insert_hof(
                agent_id=candidate.agent_id,
                inducted_tick=self.tick,
                heuristic_win_rate=candidate_wr,
            )
            self._add_hof_agent(candidate, hof_id)
        else:
            weakest = min(active_hof_records, key=lambda r: r.get("combined_score", r["heuristic_win_rate"]))
            if candidate_wr >= weakest["heuristic_win_rate"] + self.config.hof_eviction_margin:
                self.repo.evict_hof(weakest["id"], self.tick)
                self._remove_hof_agent(weakest["id"])
                hof_id = self.repo.insert_hof(
                    agent_id=candidate.agent_id,
                    inducted_tick=self.tick,
                    heuristic_win_rate=candidate_wr,
                )
                self._add_hof_agent(candidate, hof_id)

    def _find_hof_agent(self, hof_record_id: int) -> Agent | None:
        for a in self._hof_agents:
            if getattr(a, "_hof_record_id", None) == hof_record_id:
                return a
        return None

    def _add_hof_agent(self, source_agent: Agent, hof_record_id: int) -> None:
        """Add an Agent object to the in-memory HoF list (genome copied from source)."""
        hof_agent = Agent(
            source_agent.genome,
            self.config.board_columns,
            self.config.board_rows,
            agent_id=source_agent.agent_id,
        )
        hof_agent._hof_record_id = hof_record_id
        self._hof_agents.append(hof_agent)

    def _remove_hof_agent(self, hof_record_id: int) -> None:
        self._hof_agents = [
            a for a in self._hof_agents if getattr(a, "_hof_record_id", None) != hof_record_id
        ]

    def _run_benchmark(self) -> None:
        if self.tick % self.config.benchmark_every_n_ticks != 0:
            return
        if not self.alive:
            return

        best = max(self.alive, key=lambda a: a.fitness)

        all_opponents = list(_BASELINE_OPPONENTS) + [(
            get_heuristic_bot(self.config.heuristic_bot_level), "heuristic"
        )]

        for bot_fn, opponent_type in all_opponents:
            bound_bot = functools.partial(bot_fn, rng=self.rng)
            wins = losses = draws = 0

            for i in range(self.config.benchmark_games_per_opponent):
                first_mover = 1 if i % 2 == 0 else -1
                result = play_match(best.choose_move, bound_bot, first_mover=first_mover)

                if result.winner == 1:
                    db_result = "player1_win"
                    wins += 1
                elif result.winner == -1:
                    db_result = "player2_win"
                    losses += 1
                else:
                    db_result = "draw"
                    draws += 1

                self.repo.insert_game(
                    tick=self.tick,
                    player1_agent_id=best.agent_id,
                    player2_agent_id=None,
                    result=db_result,
                    num_moves=result.num_moves,
                    move_history=result.move_history,
                    game_type="benchmark",
                    opponent_label=opponent_type,
                )

            win_rate = (wins + 0.5 * draws) / self.config.benchmark_games_per_opponent
            self.repo.insert_benchmark_result(
                tick=self.tick,
                agent_id=best.agent_id,
                opponent_type=opponent_type,
                games_played=self.config.benchmark_games_per_opponent,
                win_rate=win_rate,
            )

    def _write_snapshot(self) -> None:
        fitnesses = [a.fitness for a in self.alive]
        lifespans = [a.genome.lifespan for a in self.alive]
        mutation_rates = [a.genome.mutation_rate for a in self.alive]
        best = max(self.alive, key=lambda a: a.fitness) if self.alive else None

        self.repo.insert_snapshot(
            tick=self.tick,
            population_size=len(self.alive),
            avg_fitness=sum(fitnesses) / len(fitnesses) if fitnesses else 0.0,
            max_fitness=max(fitnesses) if fitnesses else 0.0,
            min_fitness=min(fitnesses) if fitnesses else 0.0,
            avg_lifespan=sum(lifespans) / len(lifespans) if lifespans else 0.0,
            avg_mutation_rate=sum(mutation_rates) / len(mutation_rates) if mutation_rates else 0.0,
            best_agent_id=best.agent_id if best else None,
        )
