"""Market-behavior proxies derived from observable price movement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from football_ai.core.feature_engine import FeatureAnalysis
from football_ai.core.odds_engine import OddsAnalysis


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class MarketBehaviorAnalysis:
    market_bias: str
    sharp_money_signal: str
    public_money: float
    defensive_side: str
    hedge_behavior: str
    trap_indicator: float
    control_tendency: str
    direction_scores: dict[str, float]
    explanations: List[str]


class MarketBehaviorEngine:
    """Estimate crowding, defense and trap risk without claiming insider knowledge."""

    def analyze(self, features: FeatureAnalysis, odds: OddsAnalysis) -> MarketBehaviorAnalysis:
        probs = odds.current_probabilities
        favorite = max(probs, key=probs.get)
        favorite_prob = probs[favorite]
        favorite_shift = odds.probability_shifts[favorite]
        public_money = _clamp(35 + max(0.0, favorite_prob - 0.42) * 150 + max(0.0, favorite_shift) * 420)

        fundamental_signal = max(-1.0, min(1.0, features.strength_gap / 22.0))
        market_signal = odds.market_signal
        divergence = abs(fundamental_signal - market_signal)
        line_resistance = 0.0
        if favorite == "home" and odds.asian_bias != "home":
            line_resistance = 18.0
        elif favorite == "away" and odds.asian_bias != "away":
            line_resistance = 18.0
        trap = _clamp(
            12
            + max(0.0, public_money - 60) * 0.65
            + divergence * 32
            + line_resistance
            + (12 if odds.market_consistency == "分歧" else 0)
        )

        scores = {
            "home": probs["home"] + max(0.0, market_signal) * 0.13,
            "draw": probs["draw"] + (0.05 if odds.market_consistency == "分歧" else 0.0),
            "away": probs["away"] + max(0.0, -market_signal) * 0.13,
        }
        market_bias = max(scores, key=scores.get)
        defensive_side = odds.asian_bias if odds.asian_bias != "even" else market_bias
        if abs(market_signal) >= 0.22 and odds.market_consistency == "一致":
            sharp_signal = f"{market_bias} direction, moderate"
        elif odds.market_consistency == "分歧":
            sharp_signal = "mixed / unconfirmed"
        else:
            sharp_signal = "weak"

        hedge = "欧亚分流，可能存在风险对冲" if odds.market_consistency == "分歧" else "欧亚方向接近，未见明显分流"
        if trap >= 70:
            control = "高控盘/诱导风险代理"
        elif trap >= 45:
            control = "中等控盘风险代理"
        else:
            control = "常规定价波动"
        explanations = [
            f"热门拥挤度代理 {public_money:.0f}/100，当前热门方向为 {favorite}。",
            f"市场防守方向代理为 {defensive_side}；{hedge}。",
            f"诱盘风险代理 {trap:.0f}/100，主要来自热门程度、基本面与盘口背离及欧亚分歧。",
            "以上为公开赔率结构的计算解释，不代表掌握真实资金流或庄家内部意图。",
        ]
        return MarketBehaviorAnalysis(
            market_bias=market_bias,
            sharp_money_signal=sharp_signal,
            public_money=round(public_money, 1),
            defensive_side=defensive_side,
            hedge_behavior=hedge,
            trap_indicator=round(trap, 1),
            control_tendency=control,
            direction_scores={key: round(value, 4) for key, value in scores.items()},
            explanations=explanations,
        )
