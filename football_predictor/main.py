"""命令行入口：运行本地样例并输出中文分析报告。"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from football_predictor.analysis_service import generate_report
    from football_predictor.sample_data import build_sample_data
else:
    from .analysis_service import generate_report
    from .sample_data import build_sample_data


def build_report() -> str:
    match, odds_data = build_sample_data()
    return generate_report(match, odds_data)


def main() -> None:
    print(build_report())


if __name__ == "__main__":
    main()
