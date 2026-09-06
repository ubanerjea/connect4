"""Population: the live pool, running one tick (plan Sec4.2).

Wires together the game engine (Phase 1), agents/genome (Phase 2), and
storage (Phase 3). Senescence (Sec4.7, now Phase 9) is still out of scope.
"""

from __future__ import annotations

import functools

import numpy as np

from evoconnect4.agent.agent import Agent
from evoconnect4.agent.genome import Genome, crossover, decode, encode, mutate, random_genome
from evoconnect4.config import Config
from evoconnect4.game.bots import heuristic_bot, random_mover
from evoconnect4.game.match import play_match
from evoconnect4.storage.repository import Repository

_BASELINE_OPPONENTS = ((random_mover, "random"), (heuristic_bot, "heuristic"))


def reproduction_interval(fitness: float, config: Config) -> float:
    lo, hi = config.reproduction_interval_min, config.reproduction_interval_max
    interval = hi - fitness * (hi - lo)
    return min(max(interval, lo), hi)


class Population:
    def __init__(self, config: Config, repo: Repository, rng: np.random.Generator | None = None) -> None:
        self.config = config
        self.repo = repo
        self.rng = rng if rng is not None else np.random.default_rng(config.random_seed)
        self.tick = 0
        self.alive: list[Agent] = []

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
            population.alive.append(agent)

        state = repo.get_simulation_state()
        population.tick = state["current_tick"]
        return population, state["rng_state"]

    def run_tick(self) -> None:
        self.tick += 1

        for agent_a, agent_b in self._pair_alive():
            self._play_pair(agent_a, agent_b)

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
            agent_b.losses += 1
        elif result.winner == -1:
            db_result = "player2_win"
            agent_a.losses += 1
            agent_b.wins += 1
        else:
            db_result = "draw"
            agent_a.draws += 1
            agent_b.draws += 1

        agent_a.games_played += 1
        agent_b.games_played += 1
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
        )

    def _recompute_fitness(self) -> None:
        for agent in self.alive:
            if agent.games_played > 0:
                agent.fitness = (agent.wins + 0.5 * agent.draws) / agent.games_played
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

    def _run_benchmark(self) -> None:
        if self.tick % self.config.benchmark_every_n_ticks != 0:
            return
        if not self.alive:
            return

        best = max(self.alive, key=lambda a: a.fitness)

        for bot_fn, opponent_type in _BASELINE_OPPONENTS:
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
