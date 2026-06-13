"""Professional engine contracts and offline pipeline tests."""

from datetime import date
import unittest

from football_ai.config import MatchContext
from football_ai.core.match_loader import MatchLoader
from football_ai.core.report_engine import ProFootballAnalyticsEngine
from football_ai.data.mock_data import MockDataProvider


class ProEngineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = MatchLoader(api_key=None).load(date(2026, 6, 13), ["PL"])[0]
        self.odds = MockDataProvider().odds(self.fixture)

    def test_offline_pipeline_returns_normalized_probabilities(self):
        result = ProFootballAnalyticsEngine(api_key=None).analyze(self.fixture, self.odds, MatchContext())

        self.assertAlmostEqual(sum(result.probability.probabilities.values()), 100.0, places=6)
        self.assertEqual(len(result.probability.score_distribution), 6)
        self.assertAlmostEqual(sum(result.probability.goal_ranges.values()), 100.0, places=6)
        self.assertIn(result.risk.risk_level, {"LOW", "MEDIUM", "HIGH"})
        self.assertIn(result.risk.recommendation_grade, {"A", "B", "C"})
        self.assertGreaterEqual(result.market.trap_indicator, 0)
        self.assertLessEqual(result.market.trap_indicator, 100)

    def test_report_contains_required_sections_and_disclaimer(self):
        result = ProFootballAnalyticsEngine(api_key=None).analyze(self.fixture, self.odds)

        for heading in (
            "比赛信息",
            "基本面对比",
            "盘口解读",
            "市场行为判断",
            "概率预测",
            "比分模型",
            "风险等级",
            "分析优先级",
            "风险提示",
        ):
            self.assertIn(heading, result.report)
        self.assertIn("不构成投注建议", result.report)
        self.assertIn("不保证预测准确率", result.report)

    def test_match_loader_uses_mock_without_key(self):
        fixtures = MatchLoader(api_key=None).load(date(2026, 6, 13), ["WC"])

        self.assertTrue(fixtures)
        self.assertTrue(all(item.source == "mock" for item in fixtures))
        self.assertTrue(all(item.neutral_ground for item in fixtures))


if __name__ == "__main__":
    unittest.main()
