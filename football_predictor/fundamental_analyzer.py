"""球队基本面评分。"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .config import DEFAULT_CONFIG, PredictorConfig
from .models import FundamentalAnalysis, MatchInfo, TeamInfo


class FundamentalAnalyzer:
    def __init__(self, config: PredictorConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    @staticmethod
    def _recent_form_score(results: List[str]) -> float:
        if not results:
            return 50.0
        points = 0.0
        for result in results[-6:]:
            normalized = result.strip().upper()
            if normalized in {"W", "WIN", "胜"}:
                points += 3
            elif normalized in {"D", "DRAW", "平"}:
                points += 1
        return points / (len(results[-6:]) * 3) * 100

    @staticmethod
    def _injury_score(team: TeamInfo) -> float:
        injury_penalty = min(55.0, sum(item.impact for item in team.injuries) * 4.0)
        return max(0.0, min(100.0, 100.0 - injury_penalty)) * 0.7 + team.key_player_availability * 0.3

    @staticmethod
    def _head_to_head_scores(match: MatchInfo) -> Tuple[float, float]:
        h2h = match.head_to_head
        if h2h.total == 0:
            return 50.0, 50.0
        home_score = (h2h.home_wins * 3 + h2h.draws) / (h2h.total * 3) * 100
        away_score = (h2h.away_wins * 3 + h2h.draws) / (h2h.total * 3) * 100
        return home_score, away_score

    @staticmethod
    def _venue_scores(match: MatchInfo) -> Tuple[float, float]:
        home = match.home_team
        away = match.away_team
        if match.neutral_venue:
            return home.venue_performance.neutral_rating, away.venue_performance.neutral_rating
        travel_penalty = min(12.0, match.travel_distance_km / 800.0)
        return home.venue_performance.home_rating, max(0.0, away.venue_performance.away_rating - travel_penalty)

    def analyze(self, match: MatchInfo) -> FundamentalAnalysis:
        home, away = match.home_team, match.away_team
        h2h_home, h2h_away = self._head_to_head_scores(match)
        venue_home, venue_away = self._venue_scores(match)

        components: Dict[str, Tuple[float, float]] = {
            "整体实力": (home.strength_rating, away.strength_rating),
            "近期状态": (self._recent_form_score(home.recent_results), self._recent_form_score(away.recent_results)),
            "进攻能力": (home.attack_rating, away.attack_rating),
            "防守能力": (home.defense_rating, away.defense_rating),
            "伤停影响": (self._injury_score(home), self._injury_score(away)),
            "战意强弱": (match.home_motivation, match.away_motivation),
            "赛程宽松度": (100 - home.schedule_density, 100 - away.schedule_density),
            "体能状况": (home.fitness_rating, away.fitness_rating),
            "场地因素": (venue_home, venue_away),
            "历史交锋": (h2h_home, h2h_away),
            "环境适应": (
                (home.weather_adaptability + home.pitch_adaptability) / 2,
                (away.weather_adaptability + away.pitch_adaptability) / 2,
            ),
        }
        weights = self.config.fundamental_weights
        weight_map = dict(zip(components, weights.__dict__.values()))
        home_score = sum(components[key][0] * weight_map[key] for key in components)
        away_score = sum(components[key][1] * weight_map[key] for key in components)
        difference = home_score - away_score
        threshold = self.config.tendency_threshold
        tendency = "主队" if difference >= threshold else "客队" if difference <= -threshold else "平衡"

        ranked = sorted(components.items(), key=lambda item: abs(item[1][0] - item[1][1]), reverse=True)
        reasons: List[str] = []
        for factor, (home_value, away_value) in ranked[:4]:
            diff = home_value - away_value
            if abs(diff) < 3:
                reasons.append(
                    f"{factor}接近（{home.name} {home_value:.1f}，{away.name} {away_value:.1f}）"
                )
            else:
                leader = home.name if diff > 0 else away.name
                reasons.append(
                    f"{leader}在{factor}方面占优（{home.name} {home_value:.1f}，"
                    f"{away.name} {away_value:.1f}）"
                )

        return FundamentalAnalysis(
            home_score=round(home_score, 2),
            away_score=round(away_score, 2),
            tendency=tendency,
            reasons=reasons,
            components=components,
        )
