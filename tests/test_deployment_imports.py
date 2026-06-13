"""Streamlit Cloud 入口所需模块的导入冒烟测试。"""

import importlib
import unittest


class DeploymentImportTests(unittest.TestCase):
    def test_streamlit_entrypoint_dependencies_import(self):
        modules = (
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

        self.assertTrue(callable(MatchRecommender))
