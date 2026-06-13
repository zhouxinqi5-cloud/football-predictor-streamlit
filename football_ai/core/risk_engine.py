"""Multi-factor uncertainty and upset-risk model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from football_ai.config import MatchContext
from football_ai.core.feature_engine import FeatureAnalysis
from football_ai.core.market_behavior import MarketBehaviorAnalysis
from football_ai.core.odds_engine import OddsAnalysis
from football_ai.core.probability_engine import ProbabilityAnalysis


@dataclass(frozen=True)
class RiskAnalysis:
    risk_level: str
    risk_score: float
    upset_risk: float
    divergence_risk: float
    motivation_risk: float
    fake_favorite_risk: float
    situational_risk: float
    recommendation_grade: str
    factors: List[str]


class RiskEngine:
    def analyze(
        self,
        features: FeatureAnalysis,
        odds: OddsAnalysis,
        market: MarketBehaviorAnalysis,
        probability: ProbabilityAnalysis,
        context: MatchContext,
    ) -> RiskAnalysis:
        favorite_probability = max(probability.probabilities.values())
        upset = max(12.0, 72 - favorite_probability * 0.72 + market.trap_indicator * 0.20)
        fundamental_side = features.match_tendency
        divergence = 20.0
        if odds.market_consistency == "分歧":
            divergence += 28
        if fundamental_side in ("home", "away") and fundamental_side != market.market_bias:
            divergence += 30
        divergence = min(100.0, divergence)
        motivation = 18.0 if context.motivation_known else 58.0
        motivation += max(0.0, 55 - min(features.home.motivation_score, features.away.motivation_score)) * 0.35
        motivation = min(100.0, motivation)
        fake_favorite = min(100.0, market.trap_indicator * 0.82 + (18 if market.public_money >= 70 else 0))
        situational = 12.0
        factors: List[str] = []
        if context.final_group_round:
            situational += 48
            factors.append("小组赛末轮存在策略互动与同步赛果风险。")
        if context.knockout_match:
            situational += 30
            factors.append("淘汰赛可能更保守，常规时间平局与低比分权重上升。")
        situational = min(100.0, situational)
        risk = upset * 0.20 + divergence * 0.25 + motivation * 0.18 + fake_favorite * 0.24 + situational * 0.13
        risk = max(0.0, min(100.0, risk))
        level = "LOW" if risk < 36 else "MEDIUM" if risk < 64 else "HIGH"

        alignment = odds.market_consistency == "一致" and (
            features.match_tendency == "even" or features.match_tendency == market.market_bias
        )
        if level == "LOW" and probability.confidence >= 58 and alignment:
            grade = "A"
        elif level != "HIGH" and probability.confidence >= 42:
            grade = "B"
        else:
            grade = "C"
        if divergence >= 55:
            factors.append("基本面、欧赔或亚盘方向存在明显背离。")
        if market.public_money >= 70:
            factors.append("热门方向拥挤，价格继续压缩后的回报风险上升。")
        if market.trap_indicator >= 60:
            factors.append("假热门/诱盘风险代理偏高，不宜作单向确定性解释。")
        if not context.motivation_known:
            factors.append("战意未由可靠输入确认，模型仅按排名压力估计。")
        if probability.draw >= 29:
            factors.append("平局概率处于不可忽视区间。")
        if not factors:
            factors.append("未发现突出异常，但阵容与临场信息仍可能改变判断。")
        return RiskAnalysis(
            risk_level=level,
            risk_score=round(risk, 1),
            upset_risk=round(upset, 1),
            divergence_risk=round(divergence, 1),
            motivation_risk=round(motivation, 1),
            fake_favorite_risk=round(fake_favorite, 1),
            situational_risk=round(situational, 1),
            recommendation_grade=grade,
            factors=factors,
        )
