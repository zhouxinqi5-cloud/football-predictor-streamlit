"""供 CLI 和 Streamlit 复用的完整分析流水线。"""

from __future__ import annotations

from .fundamental_analyzer import FundamentalAnalyzer
from .models import MatchInfo, OddsData
from .odds_analyzer import OddsAnalyzer
from .probability_model import ProbabilityModel
from .report_generator import ReportGenerator
from .risk_analyzer import RiskAnalyzer
from .score_predictor import ScorePredictor


def generate_report(match: MatchInfo, odds_data: OddsData) -> str:
    fundamental = FundamentalAnalyzer().analyze(match)
    odds = OddsAnalyzer().analyze(odds_data, fundamental)
    probability = ProbabilityModel().predict(fundamental, odds)
    scores = ScorePredictor().predict(match, odds, probability)
    risk = RiskAnalyzer().analyze(match, fundamental, odds, probability)
    return ReportGenerator().generate(
        match=match,
        odds_data=odds_data,
        fundamental=fundamental,
        odds=odds,
        probability=probability,
        scores=scores,
        risk=risk,
    )
