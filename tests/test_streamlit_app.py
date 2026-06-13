"""Streamlit 页面在无 API Key 时的手动流程测试。"""

import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_manual_report_without_api_keys(self):
        with patch.dict(
            os.environ,
            {"FOOTBALL_DATA_API_KEY": "", "ODDS_API_KEY": "", "FOOTBALL_AI_DISABLE_EXTERNAL_APIS": "1"},
            clear=False,
        ):
            app = AppTest.from_file("app.py").run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("模拟示例数据，不是真实近期比赛" in warning.value for warning in app.warning))
            self.assertTrue(any(button.label == "刷新今日比赛" for button in app.button))
            report_button = next(button for button in app.button if button.label == "生成分析报告")
            app = report_button.click().run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        report_blocks = [code.value for code in app.code if "足球比赛预测分析报告" in code.value]
        self.assertEqual(len(report_blocks), 1)
        self.assertIn("不构成投注建议", report_blocks[0])

    def test_mock_fixture_and_feature_workflow_without_api_key(self):
        with patch.dict(
            os.environ,
            {"FOOTBALL_DATA_API_KEY": "", "ODDS_API_KEY": "", "FOOTBALL_AI_DISABLE_EXTERNAL_APIS": "1"},
            clear=False,
        ):
            app = AppTest.from_file("app.py").run(timeout=20)
            self.assertTrue(any("模拟示例数据，不是真实近期比赛" in warning.value for warning in app.warning))
            fetch_button = next(button for button in app.button if button.label == "自动获取比赛")
            app = fetch_button.click().run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            feature_button = next(button for button in app.button if button.label == "自动生成基本面评分")
            app = feature_button.click().run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        metric_labels = {metric.label for metric in app.metric}
        self.assertIn("主队基本面", metric_labels)
        self.assertIn("客队基本面", metric_labels)
        self.assertTrue(any("自动基本面已生成" in success.value for success in app.success))
        report_button = next(button for button in app.button if button.label == "生成分析报告")
        app = report_button.click().run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertTrue(any("足球比赛预测分析报告" in code.value for code in app.code))


if __name__ == "__main__":
    unittest.main()
