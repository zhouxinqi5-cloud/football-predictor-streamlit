"""Conservative probability fusion and Poisson score distribution."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from football_ai.config import ENGINE_CONFIG, EngineConfig
from football_ai.core.feature_engine import FeatureAnalysis
from football_ai.core.market_behavior import MarketBehaviorAnalysis
from football_ai.core.odds_engine import OddsAnalysis


@dataclass(frozen=True)
class ScoreProbability:
    score: str
    probability: float


@dataclass(frozen=True)
class ProbabilityAnalysis:
    home_win: float
    draw: float
    away_win: float
    home_expected_goals: float
    away_expected_goals: float
    score_distribution: List[ScoreProbability]
    goal_ranges: Dict[str, float]
    confidence: float
    fusion_notes: List[str]

    @property
    def probabilities(self) -> Dict[str, float]:
        return {"home": self.home_win, "draw": self.draw, "away": self.away_win}


def _normalize(values: Dict[str, float]) -> Dict[str, float]:
    positive = {key: max(0.001, value) for key, value in values.items()}
    total = sum(positive.values())
    return {key: value / total for key, value in positive.items()}


def _rounded_percent(values: Dict[str, float]) -> Dict[str, float]:
    result = {key: round(value * 100, 2) for key, value in values.items()}
    difference = round(100.0 - sum(result.values()), 2)
    result[max(result, key=result.get)] = round(result[max(result, key=result.get)] + difference, 2)
    return result


class ProbabilityEngine:
    def __init__(self, config: EngineConfig = ENGINE_CONFIG) -> None:
        self.config = config

    @staticmethod
    def _fundamental_vector(features: FeatureAnalysis) -> Dict[str, float]:
        gap = features.strength_gap
        home = 1 / (1 + math.exp(-(gap + 1.8) / 9.5))
        draw = max(0.18, 0.31 - min(abs(gap), 24) * 0.005)
        return _normalize({"home": home * (1 - draw), "draw": draw, "away": (1 - home) * (1 - draw)})

    @staticmethod
    def _market_vector(market: MarketBehaviorAnalysis) -> Dict[str, float]:
        vector = dict(market.direction_scores)
        if market.trap_indicator >= 60:
            favorite = max(vector, key=vector.get)
            vector[favorite] *= 1 - min(0.16, (market.trap_indicator - 55) / 300)
            vector["draw"] *= 1.08
        return _normalize(vector)

    @staticmethod
    def _poisson_probability(goals: int, expectation: float) -> float:
        return math.exp(-expectation) * expectation**goals / math.factorial(goals)

    def analyze(
        self,
        features: FeatureAnalysis,
        odds: OddsAnalysis,
        market: MarketBehaviorAnalysis,
    ) -> ProbabilityAnalysis:
        fundamental = self._fundamental_vector(features)
        odds_vector = odds.current_probabilities
        market_vector = self._market_vector(market)
        weights = self.config.weights
        fused = _normalize({
            key: fundamental[key] * weights.fundamentals
            + odds_vector[key] * weights.odds
            + market_vector[key] * weights.market_behavior
            for key in ("home", "draw", "away")
        })

        conflict = odds.market_consistency == "分歧" or (
            features.match_tendency in ("home", "away") and features.match_tendency != market.market_bias
        )
        shrinkage = self.config.conservative_shrinkage
        if conflict:
            shrinkage += self.config.conflict_shrinkage
        shrinkage += self.config.trap_shrinkage * market.trap_indicator / 100
        fused = _normalize({key: value * (1 - shrinkage) + (1 / 3) * shrinkage for key, value in fused.items()})
        percent = _rounded_percent(fused)

        raw_total = max(1.2, min(4.2, odds.expected_goals_current))
        base_home = features.home.goal_expectancy
        base_away = features.away.goal_expectancy
        ratio_total = max(0.4, base_home + base_away)
        home_xg = raw_total * base_home / ratio_total
        away_xg = raw_total * base_away / ratio_total
        result_edge = (fused["home"] - fused["away"]) * 0.48
        home_xg = max(0.2, home_xg + result_edge)
        away_xg = max(0.2, away_xg - result_edge)
        rescale = raw_total / (home_xg + away_xg)
        home_xg, away_xg = home_xg * rescale, away_xg * rescale

        score_rows: List[Tuple[str, float, int]] = []
        max_goals = self.config.score_max_goals
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                probability = self._poisson_probability(home_goals, home_xg) * self._poisson_probability(away_goals, away_xg)
                score_rows.append((f"{home_goals}-{away_goals}", probability, home_goals + away_goals))
        score_rows.sort(key=lambda item: item[1], reverse=True)
        candidates = [ScoreProbability(score, round(probability * 100, 2)) for score, probability, _ in score_rows[: self.config.score_candidates]]
        ranges = {
            "0-1球": sum(probability for _, probability, total in score_rows if total <= 1),
            "2-3球": sum(probability for _, probability, total in score_rows if 2 <= total <= 3),
            "4球以上": sum(probability for _, probability, total in score_rows if total >= 4),
        }
        range_percent = _rounded_percent(_normalize(ranges))
        spread = max(fused.values()) - min(fused.values())
        confidence = max(20.0, min(85.0, 42 + spread * 62 - market.trap_indicator * 0.18 - (8 if conflict else 0)))
        return ProbabilityAnalysis(
            home_win=percent["home"],
            draw=percent["draw"],
            away_win=percent["away"],
            home_expected_goals=round(home_xg, 2),
            away_expected_goals=round(away_xg, 2),
            score_distribution=candidates,
            goal_ranges=range_percent,
            confidence=round(confidence, 1),
            fusion_notes=[
                "融合权重：基本面 50%，赔率 25%，市场行为代理 25%。",
                f"保守收缩系数 {shrinkage:.2f}；{'存在方向冲突' if conflict else '主要方向未见明显冲突'}。",
                "比分分布使用独立泊松近似，xG 为球队数据与大小球盘口构造的代理值。",
            ],
        )
