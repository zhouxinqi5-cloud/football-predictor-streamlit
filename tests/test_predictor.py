"""核心流程回归测试。"""

import unittest
from dataclasses import replace

from football_predictor.fundamental_analyzer import FundamentalAnalyzer
from football_predictor.main import build_report
from football_predictor.odds_analyzer import OddsAnalyzer
from football_predictor.probability_model import ProbabilityModel
from football_predictor.risk_analyzer import RiskAnalyzer
from football_predictor.sample_data import build_sample_data
from football_predictor.score_predictor import ScorePredictor


class PredictorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.match, self.odds_data = build_sample_data()
        self.fundamental = FundamentalAnalyzer().analyze(self.match)
        self.odds = OddsAnalyzer().analyze(self.odds_data, self.fundamental)
        self.probability = ProbabilityModel().predict(self.fundamental, self.odds)

    def test_probabilities_sum_to_100(self) -> None:
        total = self.probability.home_win + self.probability.draw + self.probability.away_win
        self.assertAlmostEqual(total, 100.0, places=2)

    def test_analysis_style_is_fundamental_first_and_conservative(self) -> None:
        weights = self.probability.component_weights
        self.assertEqual(weights["基本面"], 0.55)
        self.assertGreater(weights["基本面"], weights["欧赔"])
        self.assertGreaterEqual(self.probability.diagnostics.conservative_shrinkage, 0.05)
        self.assertTrue(self.probability.diagnostics.fundamental_market_alignment)
        self.assertTrue(self.probability.diagnostics.european_asian_alignment)

    def test_conflicting_signals_increase_conservative_shrinkage(self) -> None:
        fundamental = replace(
            self.fundamental,
            home_score=86.0,
            away_score=74.0,
            tendency="主队",
        )
        european = replace(self.odds.european, tendency="主胜")
        asian = replace(self.odds.asian, tendency="客队", home_bias=-0.65)
        conflicting_odds = replace(self.odds, european=european, asian=asian)
        prediction = ProbabilityModel().predict(fundamental, conflicting_odds)

        self.assertGreaterEqual(prediction.diagnostics.conflict_count, 2)
        self.assertGreater(prediction.diagnostics.conservative_shrinkage, 0.05)
        self.assertIn("分歧", prediction.diagnostics.european_asian_alignment)

    def test_score_ranges_sum_to_100(self) -> None:
        result = ScorePredictor().predict(self.match, self.odds, self.probability)
        self.assertAlmostEqual(sum(result.goal_ranges.values()), 100.0, places=2)
        self.assertGreaterEqual(len(result.candidates), 3)
        self.assertLessEqual(len(result.candidates), 5)

    def test_report_contains_required_sections_and_disclaimer(self) -> None:
        report = build_report()
        for section in range(1, 10):
            self.assertIn(f"【{section}.", report)
        self.assertIn("不构成投注建议", report)
        self.assertIn("不保证准确率", report)
        self.assertIn("基本面为主，盘口和指数为辅", report)
        self.assertIn("基本面与盘口", report)
        self.assertIn("热门方向", report)
        self.assertIn("欧赔与亚盘", report)
        self.assertIn("保守调整", report)
        for forbidden in ("必胜", "稳赚", "稳胆"):
            self.assertNotIn(forbidden, report)

    def test_risk_level_is_supported(self) -> None:
        result = RiskAnalyzer().analyze(self.match, self.fundamental, self.odds, self.probability)
        self.assertIn(result.level, {"低", "中", "高"})


if __name__ == "__main__":
    unittest.main()
