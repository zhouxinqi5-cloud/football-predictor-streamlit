"""基于攻防评分和大小球市场预期的泊松比分模型。"""

from __future__ import annotations

import math
from typing import List, Tuple

from .config import DEFAULT_CONFIG, PredictorConfig
from .models import MatchInfo, OddsAnalysis, ProbabilityPrediction, ScoreCandidate, ScorePrediction


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ScorePredictor:
    def __init__(self, config: PredictorConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    @staticmethod
    def _poisson(goals: int, expected: float) -> float:
        return math.exp(-expected) * expected**goals / math.factorial(goals)

    def predict(
        self,
        match: MatchInfo,
        odds: OddsAnalysis,
        probability: ProbabilityPrediction,
    ) -> ScorePrediction:
        home, away = match.home_team, match.away_team
        home_attack_factor = 0.65 + home.attack_rating / 100
        away_attack_factor = 0.65 + away.attack_rating / 100
        away_vulnerability = 1.40 - away.defense_rating / 100
        home_vulnerability = 1.40 - home.defense_rating / 100
        home_raw = home_attack_factor * away_vulnerability
        away_raw = away_attack_factor * home_vulnerability
        if not match.neutral_venue:
            home_raw *= 1.08
            away_raw *= 0.96

        attack_total = _clamp(2.60 * (home_raw + away_raw) / 2, 1.4, 4.2)
        market_total = odds.totals.current_expected_goals
        expected_total = _clamp(market_total * 0.72 + attack_total * 0.28, 0.8, 5.0)
        raw_share = home_raw / (home_raw + away_raw)
        outcome_adjustment = (probability.home_win - probability.away_win) / 100 * 0.12
        home_share = _clamp(raw_share + outcome_adjustment, 0.28, 0.72)
        home_expected = expected_total * home_share
        away_expected = expected_total - home_expected

        score_probabilities: List[Tuple[str, float]] = []
        max_goals = self.config.max_score_per_team
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                value = self._poisson(home_goals, home_expected) * self._poisson(away_goals, away_expected)
                score_probabilities.append((f"{home_goals}-{away_goals}", value))
        score_probabilities.sort(key=lambda item: item[1], reverse=True)

        candidates = []
        for score, value in score_probabilities[: self.config.score_candidate_count]:
            percentage = value * 100
            low = max(0.0, percentage - 1.5)
            high = min(100.0, percentage + 1.5)
            candidates.append(
                ScoreCandidate(
                    score=score,
                    estimated_probability=round(percentage, 2),
                    probability_range=f"{low:.1f}%–{high:.1f}%",
                )
            )

        p_zero = self._poisson(0, expected_total)
        p_one = self._poisson(1, expected_total)
        p_two = self._poisson(2, expected_total)
        p_three = self._poisson(3, expected_total)
        goal_ranges = {
            "0-1球": round((p_zero + p_one) * 100, 2),
            "2-3球": round((p_two + p_three) * 100, 2),
            "4球以上": round(max(0.0, 1 - p_zero - p_one - p_two - p_three) * 100, 2),
        }
        rounding_gap = round(100.0 - sum(goal_ranges.values()), 2)
        largest = max(goal_ranges, key=goal_ranges.get)
        goal_ranges[largest] = round(goal_ranges[largest] + rounding_gap, 2)

        return ScorePrediction(
            home_expected_goals=round(home_expected, 2),
            away_expected_goals=round(away_expected, 2),
            candidates=candidates,
            goal_ranges=goal_ranges,
        )
