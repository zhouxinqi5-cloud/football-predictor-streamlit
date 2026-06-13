"""Explainable European, Asian-handicap and totals market analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from football_ai.config import OddsInput
from football_ai.core.feature_engine import FeatureAnalysis


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _probabilities(home: float, draw: float, away: float) -> Dict[str, float]:
    raw = {"home": 1 / home, "draw": 1 / draw, "away": 1 / away}
    total = sum(raw.values())
    return {key: value / total for key, value in raw.items()}


@dataclass(frozen=True)
class OddsAnalysis:
    opening_probabilities: Dict[str, float]
    current_probabilities: Dict[str, float]
    probability_shifts: Dict[str, float]
    opening_return_rate: float
    current_return_rate: float
    favorite_direction: str
    hot_direction: str
    asian_pattern: str
    asian_bias: str
    asian_signal: float
    handicap_change: float
    home_water_change: float
    away_water_change: float
    totals_tendency: str
    totals_signal: float
    expected_goals_opening: float
    expected_goals_current: float
    market_consistency: str
    market_signal: float
    explanations: List[str]


class OddsEngine:
    """Interpret price movement as market evidence, never as certainty."""

    @staticmethod
    def _asian_pattern(odds: OddsInput) -> str:
        line_change = odds.asian_current.handicap - odds.asian_opening.handicap
        water_change = odds.asian_current.home_water - odds.asian_opening.home_water
        if line_change < -0.01:
            return "升盘不升水" if water_change <= 0.01 else "升盘升水"
        if line_change > 0.01:
            return "降盘降水" if water_change < -0.01 else "降盘升水"
        if water_change <= -0.04:
            return "平盘降水"
        if water_change >= 0.04:
            return "平盘升水"
        return "盘口稳定"

    def analyze(self, odds: OddsInput, features: Optional[FeatureAnalysis] = None) -> OddsAnalysis:
        opening = _probabilities(
            odds.european_opening.home,
            odds.european_opening.draw,
            odds.european_opening.away,
        )
        current = _probabilities(
            odds.european_current.home,
            odds.european_current.draw,
            odds.european_current.away,
        )
        shifts = {key: current[key] - opening[key] for key in opening}
        opening_return = 1 / sum(1 / value for value in odds.european_opening.__dict__.values())
        current_return = 1 / sum(1 / value for value in odds.european_current.__dict__.values())
        favorite = max(current, key=current.get)
        hot = max(shifts, key=shifts.get)

        line_change = odds.asian_current.handicap - odds.asian_opening.handicap
        home_water_change = odds.asian_current.home_water - odds.asian_opening.home_water
        away_water_change = odds.asian_current.away_water - odds.asian_opening.away_water
        asian_signal = _clamp(-line_change * 1.45 - home_water_change * 1.8 + away_water_change * 0.9)
        asian_bias = "home" if asian_signal > 0.08 else "away" if asian_signal < -0.08 else "even"
        pattern = self._asian_pattern(odds)

        total_line_change = odds.totals_current.line - odds.totals_opening.line
        over_water_change = odds.totals_current.over_water - odds.totals_opening.over_water
        totals_signal = _clamp(total_line_change * 0.8 - over_water_change * 1.4)
        totals_tendency = "over" if totals_signal > 0.06 else "under" if totals_signal < -0.06 else "neutral"
        expected_opening = max(0.5, odds.totals_opening.line - (odds.totals_opening.over_water - odds.totals_opening.under_water) * 0.25)
        expected_current = max(0.5, odds.totals_current.line - (odds.totals_current.over_water - odds.totals_current.under_water) * 0.25)

        european_signal = _clamp((shifts["home"] - shifts["away"]) * 8.0)
        market_signal = _clamp(european_signal * 0.58 + asian_signal * 0.42)
        euro_bias = "home" if european_signal > 0.05 else "away" if european_signal < -0.05 else "even"
        consistency = "一致" if euro_bias == asian_bias or "even" in (euro_bias, asian_bias) else "分歧"

        explanations = [
            f"欧赔归一概率变化：主 {shifts['home'] * 100:+.2f}，平 {shifts['draw'] * 100:+.2f}，客 {shifts['away'] * 100:+.2f} 个百分点。",
            f"亚盘结构为“{pattern}”，主队方向信号 {asian_signal:+.2f}。",
            f"大小球预期由 {expected_opening:.2f} 调整至 {expected_current:.2f}，倾向 {totals_tendency}。",
        ]
        if features is not None:
            fundamental_bias = "home" if features.strength_gap > 4 else "away" if features.strength_gap < -4 else "even"
            explanations.append(f"基本面方向 {fundamental_bias}，欧亚市场方向一致性：{consistency}。")
            if fundamental_bias == "home" and odds.asian_current.handicap > -0.25:
                explanations.append("主队基本面占优但让步偏浅，存在强方让步不足风险。")
            elif fundamental_bias == "away" and odds.asian_current.handicap < 0.25:
                explanations.append("客队基本面占优但客向让步不足，需防市场定价保守。")

        return OddsAnalysis(
            opening_probabilities=opening,
            current_probabilities=current,
            probability_shifts=shifts,
            opening_return_rate=round(opening_return * 100, 2),
            current_return_rate=round(current_return * 100, 2),
            favorite_direction=favorite,
            hot_direction=hot,
            asian_pattern=pattern,
            asian_bias=asian_bias,
            asian_signal=round(asian_signal, 3),
            handicap_change=round(line_change, 2),
            home_water_change=round(home_water_change, 3),
            away_water_change=round(away_water_change, 3),
            totals_tendency=totals_tendency,
            totals_signal=round(totals_signal, 3),
            expected_goals_opening=round(expected_opening, 2),
            expected_goals_current=round(expected_current, 2),
            market_consistency=consistency,
            market_signal=round(market_signal, 3),
            explanations=explanations,
        )
