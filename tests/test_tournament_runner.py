from unittest import TestCase

from wingspan_ai.agents import GreedyBaselineAgent, RandomLegalAgent
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.simulation import run_tournament


class TournamentRunnerTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_sample_catalog()

    def test_tournament_runner_summarizes_matchup(self) -> None:
        result = run_tournament(
            self.catalog,
            [
                lambda seed, _player_index: RandomLegalAgent(
                    agent_id="random_legal", random_seed=seed
                ),
                lambda _seed, _player_index: GreedyBaselineAgent(agent_id="greedy"),
            ],
            seeds=[1, 2],
            tournament_id="test_tournament",
        )

        self.assertEqual(result.summary.games_played, 2)
        self.assertIn("random_legal", result.summary.mean_scores)
        self.assertIn("greedy", result.summary.mean_scores)
        self.assertEqual(sum(result.summary.win_counts.values()), 2)
