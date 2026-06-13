"""Streamlit Cloud 入口所需模块的导入冒烟测试。"""

import importlib
import unittest


class DeploymentImportTests(unittest.TestCase):
    def test_streamlit_entrypoint_dependencies_import(self):
        modules = (
            "football_ai.config",
            "football_ai.data.api_client",
            "football_ai.data.mock_data",
            "football_ai.team_name_mapper",
            "football_ai.core.match_loader",
            "football_ai.core.feature_engine",
            "football_ai.core.odds_engine",
            "football_ai.core.market_behavior",
            "football_ai.core.probability_engine",
            "football_ai.core.risk_engine",
            "football_ai.core.report_engine",
            "football_ai.ui.app",
            "football_predictor.analysis_service",
            "football_predictor.data_fetcher",
            "football_predictor.feature_engine",
            "football_predictor.fixture_fetcher",
            "football_predictor.match_recommender",
            "football_predictor.models",
            "football_predictor.odds_fetcher",
        )
        for module_name in modules:
            with self.subTest(module=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

        from football_predictor.match_recommender import MatchRecommender
        from football_ai.core.report_engine import ProFootballAnalyticsEngine

        self.assertTrue(callable(MatchRecommender))
        self.assertTrue(callable(ProFootballAnalyticsEngine))
