"""从赛程中筛选更值得深入分析的比赛，不输出投注指令。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .feature_engine import MatchFeatureResult
from .fixture_fetcher import Fixture


@dataclass(frozen=True)
class MatchRecommendation:
    fixture: Fixture
    analysis_priority: float
    strength_gap: float
    volatility_proxy: float
    category: str
    reasons: List[str]


class MatchRecommender:
    @staticmethod
    def _fallback_metrics(fixture: Fixture) -> tuple[float, float]:
        if fixture.home_position and fixture.away_position:
            gap = min(30.0, abs(fixture.home_position - fixture.away_position) * 2.2)
            closeness = max(0.0, 100 - abs(fixture.home_position - fixture.away_position) * 8)
        else:
            digest = hashlib.sha256(fixture.fixture_id.encode()).digest()
            gap = digest[0] / 255 * 24
            closeness = digest[1] / 255 * 100
        volatility = min(100.0, closeness * 0.72 + (12 if fixture.neutral_venue else 0) + 10)
        return gap, volatility

    def recommend(
        self,
        fixtures: Iterable[Fixture],
        features: Optional[Dict[str, MatchFeatureResult]] = None,
        limit: int = 5,
    ) -> List[MatchRecommendation]:
        recommendations: List[MatchRecommendation] = []
        feature_map = features or {}
        for fixture in fixtures:
            feature = feature_map.get(fixture.fixture_id)
            if feature:
                gap = abs(feature.total_strength_diff)
                pressure_difference = abs(feature.home.pressure_index - feature.away.pressure_index)
                fatigue_difference = abs(feature.home.fatigue_index - feature.away.fatigue_index)
                volatility = max(0.0, min(100.0, 92 - gap * 4 + pressure_difference * 0.25 + fatigue_difference * 0.30))
            else:
                gap, volatility = self._fallback_metrics(fixture)

            strong_candidate = gap >= 8
            volatile_candidate = volatility >= 65
            if strong_candidate and volatile_candidate:
                category = "强弱差明显且存在波动空间"
            elif strong_candidate:
                category = "强弱差明显"
            elif volatile_candidate:
                category = "波动代理较高"
            else:
                category = "常规观察"
            priority = min(100.0, max(gap * 4.2, volatility * 0.82) + (5 if fixture.neutral_venue else 0))
            reasons = [f"强弱差指标 {gap:.1f}", f"波动代理 {volatility:.1f}"]
            if feature:
                reasons.append(f"自动基本面倾向 {feature.basic_trend}")
            else:
                reasons.append("尚未计算完整基本面，优先级基于排名/稳定代理")
            recommendations.append(
                MatchRecommendation(
                    fixture=fixture,
                    analysis_priority=round(priority, 2),
                    strength_gap=round(gap, 2),
                    volatility_proxy=round(volatility, 2),
                    category=category,
                    reasons=reasons,
                )
            )
        recommendations.sort(key=lambda item: item.analysis_priority, reverse=True)
        return recommendations[: max(1, limit)]
