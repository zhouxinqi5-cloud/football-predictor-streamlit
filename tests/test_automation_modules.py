"""自动赛程、特征工程和推荐器测试。"""

import unittest
from datetime import date

from football_predictor.feature_engine import FeatureEngine
from football_predictor.fixture_fetcher import FixtureFetcher
from football_predictor.match_recommender import MatchRecommender


class AutomationModuleTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = FixtureFetcher(api_key="").fetch(date(2026, 6, 13), ["PL", "PD", "WC"])

    def test_fixture_fetcher_returns_mock_without_api_key(self):
        self.assertGreaterEqual(len(self.fixtures), 3)
        self.assertTrue(all(item.source == "mock" for item in self.fixtures))
        self.assertTrue(all(item.home_team and item.away_team for item in self.fixtures))
        self.assertTrue(any(item.neutral_venue for item in self.fixtures if item.competition_code == "WC"))

    def test_feature_engine_outputs_required_scores(self):
        result = FeatureEngine(api_key="").build_for_fixture(self.fixtures[0])

        self.assertGreaterEqual(result.home_basic_score, 0)
        self.assertLessEqual(result.home_basic_score, 100)
        self.assertGreaterEqual(result.away_basic_score, 0)
        self.assertLessEqual(result.away_basic_score, 100)
        self.assertAlmostEqual(
            result.total_strength_diff,
            result.home_basic_score - result.away_basic_score,
            places=2,
        )
        self.assertIn(result.basic_trend, {"home", "away", "even"})
        self.assertEqual(len(result.home.recent_results), 5)
        self.assertGreaterEqual(result.home.matches_last_14_days, 0)

    def test_recommender_returns_top_five_or_less(self):
        feature = FeatureEngine(api_key="").build_for_fixture(self.fixtures[0])
        recommendations = MatchRecommender().recommend(
            self.fixtures,
            {self.fixtures[0].fixture_id: feature},
            limit=5,
        )

        self.assertGreater(len(recommendations), 0)
        self.assertLessEqual(len(recommendations), 5)
        priorities = [item.analysis_priority for item in recommendations]
        self.assertEqual(priorities, sorted(priorities, reverse=True))
        self.assertTrue(all(item.reasons for item in recommendations))


if __name__ == "__main__":
    unittest.main()
