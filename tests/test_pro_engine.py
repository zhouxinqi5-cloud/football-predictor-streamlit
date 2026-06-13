"""Professional engine contracts and offline pipeline tests."""

from datetime import date
import unittest
from unittest.mock import patch

from football_ai.config import MatchContext
from football_ai.core.match_loader import MatchLoader
from football_ai.core.report_engine import ProFootballAnalyticsEngine
from football_ai.data.mock_data import MockDataProvider
from football_ai.data.thesportsdb_client import TheSportsDBClient
from football_ai.team_name_mapper import display_league_name, display_team_name
from football_predictor.data_fetcher import FootballDataError


class ProEngineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = MatchLoader(api_key=None, enable_fallback_apis=False).load(date(2026, 6, 13), ["PL"])[0]
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
        result = MatchLoader(api_key=None, enable_fallback_apis=False).load_with_status(date(2026, 6, 13), ["WC"])
        fixtures = result.fixtures

        self.assertTrue(fixtures)
        self.assertTrue(all(item.source == "mock" for item in fixtures))
        self.assertTrue(all(item.neutral_ground for item in fixtures))
        self.assertFalse(result.api_configured)
        self.assertIn("FOOTBALL_DATA_API_KEY", result.fallback_reason)

    def test_api_failure_exposes_reason_before_mock_fallback(self):
        loader = MatchLoader(api_key="configured-test-key", enable_fallback_apis=False)
        with patch.object(loader.football_data, "get_matches_by_date", side_effect=FootballDataError("测试限流")):
            result = loader.load_with_status(date(2026, 6, 13), ["PL"])

        self.assertFalse(result.is_real_data)
        self.assertTrue(result.api_configured)
        self.assertIn("测试限流", result.fallback_reason)
        self.assertTrue(all(item.source == "mock" for item in result.fixtures))

    def test_chinese_name_mapping_and_untranslated_marker(self):
        self.assertEqual(display_team_name("Arsenal FC"), "阿森纳")
        self.assertEqual(display_team_name("Brazil"), "巴西")
        self.assertEqual(display_team_name("自定义中文队"), "自定义中文队")
        self.assertEqual(display_team_name("Unknown United"), "Unknown United（未翻译）")
        self.assertEqual(display_league_name("Premier League"), "英格兰足球超级联赛")

    def test_thesportsdb_real_fixture_parser(self):
        client = TheSportsDBClient()
        payload = {
            "events": [{
                "idEvent": "100",
                "idLeague": "4328",
                "strLeague": "English Premier League",
                "strHomeTeam": "Arsenal FC",
                "strAwayTeam": "Chelsea FC",
                "idHomeTeam": "1",
                "idAwayTeam": "2",
                "strTimestamp": "2026-06-13T12:00:00Z",
            }]
        }
        with patch.object(client, "_request", return_value=payload):
            fixtures = client.get_matches_by_date(date(2026, 6, 13), ["PL"])

        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0].source, "thesportsdb")
        self.assertEqual(fixtures[0].home_team, "Arsenal FC")


if __name__ == "__main__":
    unittest.main()
