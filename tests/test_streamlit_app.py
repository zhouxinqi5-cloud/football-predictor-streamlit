"""Streamlit 页面在无 API Key 时的手动流程测试。"""

import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_manual_report_without_api_keys(self):
        with patch.dict(
            os.environ,
            {"FOOTBALL_DATA_API_KEY": "", "ODDS_API_KEY": ""},
            clear=False,
        ):
            app = AppTest.from_file("app.py").run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            report_button = next(button for button in app.button if button.label == "生成分析报告")
            app = report_button.click().run(timeout=20)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.code), 1)
        self.assertIn("足球比赛预测分析报告", app.code[0].value)
        self.assertIn("不构成投注建议", app.code[0].value)


if __name__ == "__main__":
    unittest.main()
