"""Professional-grade, explainable fundamentals feature engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from football_ai.config import ENGINE_CONFIG, EngineConfig, MatchContext, MatchFixture, TeamDataset, TeamMotivation
from football_ai.data.api_client import ApiClient
from football_ai.data.mock_data import MockDataProvider
from football_predictor.data_fetcher import FootballDataError


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class TeamPowerProfile:
    team_name: str
    elo_like_rating: float
    elo_score: float
    recent_form_score: float
    attack_strength: float
    defense_strength: float
    goal_expectancy: float
    venue_score: float
    fatigue_index: float
    travel_penalty: float
    title_race_pressure: float
    relegation_pressure: float
    qualification_pressure: float
    motivation_score: float
    power_score: float
    recent_results: List[str]
    goals_for_last10: int
    goals_against_last10: int
    clean_sheets_last10: int
    matches_last14: int
    home_win_rate: float
    away_win_rate: float
    position: Optional[int]
    points: Optional[int]


@dataclass(frozen=True)
class FeatureAnalysis:
    home: TeamPowerProfile
    away: TeamPowerProfile
    home_power_score: float
    away_power_score: float
    strength_gap: float
    match_tendency: str
    source: str
    explanations: List[str]


class FeatureEngine:
    def __init__(self, api_key: Optional[str] = None, config: EngineConfig = ENGINE_CONFIG) -> None:
        self.config = config
        self.api = ApiClient(api_key=api_key)
        self.mock = MockDataProvider()

    @staticmethod
    def _date(match: Dict) -> datetime:
        value = match.get("utcDate") or "1970-01-01T00:00:00Z"
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _match_values(match: Dict, team_id: int) -> Tuple[bool, int, int, Optional[int]]:
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        score = match.get("score", {}).get("fullTime", {})
        home_goals, away_goals = score.get("home"), score.get("away")
        is_home = home.get("id") == team_id
        opponent_id = away.get("id") if is_home else home.get("id")
        if home_goals is None or away_goals is None:
            return is_home, 0, 0, opponent_id
        return (
            (True, int(home_goals), int(away_goals), opponent_id)
            if is_home
            else (False, int(away_goals), int(home_goals), opponent_id)
        )

    @staticmethod
    def _derived_motivation(position: Optional[int], total_teams: int) -> TeamMotivation:
        if position is None:
            return TeamMotivation()
        title = _clamp(100 - (position - 1) * 22) if position <= 4 else 20.0
        qualification = _clamp(95 - abs(position - 4) * 13) if position <= 8 else 25.0
        danger_start = max(2, total_teams - 4)
        relegation = _clamp(55 + (position - danger_start) * 16) if position >= danger_start else 15.0
        return TeamMotivation(title, relegation, qualification, 62.0)

    def _profile(
        self,
        dataset: TeamDataset,
        fixture: MatchFixture,
        is_home: bool,
        motivation: TeamMotivation,
        travel_km: float,
    ) -> TeamPowerProfile:
        matches = sorted(dataset.matches, key=self._date, reverse=True)
        recent = matches[:10]
        total_teams = max(8, len(dataset.standings_by_team_id))
        result_values: List[str] = []
        weighted_points = weighted_max = weighted_goals = weighted_conceded = 0.0
        goals_for = goals_against = clean_sheets = 0
        home_games = home_wins = away_games = away_wins = 0
        for index, match in enumerate(recent):
            match_home, scored, conceded, opponent_id = self._match_values(match, dataset.team_id)
            result = "W" if scored > conceded else "L" if scored < conceded else "D"
            result_values.append(result)
            base_weight = max(0.55, 1.0 - index * 0.045)
            opponent_position = dataset.standings_by_team_id.get(opponent_id or -1, {}).get("position")
            if opponent_position is None:
                opponent_factor = 1.0
            else:
                opponent_factor = _clamp(1.18 - (opponent_position - 1) / max(1, total_teams - 1) * 0.36, 0.82, 1.18)
            points = 3 if result == "W" else 1 if result == "D" else 0
            weighted_points += points * base_weight * opponent_factor
            weighted_max += 3 * base_weight * opponent_factor
            weighted_goals += scored * base_weight * opponent_factor
            weighted_conceded += conceded * base_weight / opponent_factor
            goals_for += scored
            goals_against += conceded
            clean_sheets += int(conceded == 0)
            if match_home:
                home_games += 1
                home_wins += int(result == "W")
            else:
                away_games += 1
                away_wins += int(result == "W")

        sample = max(1, len(recent))
        recent_form = _clamp(25 + (weighted_points / weighted_max if weighted_max else 0.45) * 72)
        avg_weighted_goals = weighted_goals / max(0.1, sum(max(0.55, 1.0 - i * 0.045) for i in range(sample)))
        avg_weighted_conceded = weighted_conceded / max(0.1, sum(max(0.55, 1.0 - i * 0.045) for i in range(sample)))
        season_played = dataset.played_games or 1
        season_gf = (dataset.goals_for or round(1.35 * season_played)) / season_played
        season_ga = (dataset.goals_against or round(1.25 * season_played)) / season_played
        attack = _clamp(35 + (avg_weighted_goals * 0.65 + season_gf * 0.35) / 1.45 * 45)
        defense = _clamp(88 - (avg_weighted_conceded * 0.65 + season_ga * 0.35) / 1.35 * 37 + clean_sheets / sample * 12)
        home_rate = home_wins / home_games if home_games else 0.48
        away_rate = away_wins / away_games if away_games else 0.36
        venue_rate = home_rate if is_home and not fixture.neutral_ground else away_rate if not fixture.neutral_ground else (home_rate + away_rate) / 2
        venue_score = _clamp(40 + venue_rate * 50 + (5 if is_home and not fixture.neutral_ground else 0))

        played = dataset.played_games or 1
        points_per_game = (dataset.points or round(1.35 * played)) / played
        goal_difference_per_game = ((dataset.goals_for or 0) - (dataset.goals_against or 0)) / played
        position_bonus = max(-90.0, 115.0 - (dataset.position or total_teams // 2) * 10.5)
        elo = 1420 + points_per_game * 92 + goal_difference_per_game * 45 + position_bonus + (recent_form - 50) * 1.7
        elo_score = _clamp(50 + (elo - 1500) / 9.0)

        kickoff_utc = fixture.kickoff_time.astimezone(timezone.utc) if fixture.kickoff_time.tzinfo else fixture.kickoff_time.replace(tzinfo=timezone.utc)
        cutoff = kickoff_utc - timedelta(days=14)
        matches_last14 = sum(1 for match in matches if cutoff <= self._date(match) < kickoff_utc)
        fatigue = _clamp(max(0, matches_last14 - 2) * 18 + max(0, matches_last14 - 4) * 8)
        travel_penalty = _clamp(travel_km / 240.0, 0, 25)
        motivation_score = _clamp(
            motivation.title_race_pressure * 0.35
            + motivation.relegation_pressure * 0.30
            + motivation.qualification_pressure * 0.35
        )
        weights = self.config.feature_weights
        power = (
            elo_score * weights.elo
            + recent_form * weights.recent_form
            + attack * weights.attack
            + defense * weights.defense
            + venue_score * weights.venue
            + (100 - fatigue) * weights.freshness
            + motivation_score * weights.motivation
            + (100 - travel_penalty * 4) * weights.travel
        )
        goal_expectancy = _clamp(0.25 + attack / 100 * 2.15 + (100 - defense) / 100 * 0.25, 0.35, 3.20)
        return TeamPowerProfile(
            team_name=dataset.team_name,
            elo_like_rating=round(elo, 1),
            elo_score=round(elo_score, 2),
            recent_form_score=round(recent_form, 2),
            attack_strength=round(attack, 2),
            defense_strength=round(defense, 2),
            goal_expectancy=round(goal_expectancy, 2),
            venue_score=round(venue_score, 2),
            fatigue_index=round(fatigue, 2),
            travel_penalty=round(travel_penalty, 2),
            title_race_pressure=motivation.title_race_pressure,
            relegation_pressure=motivation.relegation_pressure,
            qualification_pressure=motivation.qualification_pressure,
            motivation_score=round(motivation_score, 2),
            power_score=round(power, 2),
            recent_results=result_values,
            goals_for_last10=goals_for,
            goals_against_last10=goals_against,
            clean_sheets_last10=clean_sheets,
            matches_last14=matches_last14,
            home_win_rate=round(home_rate * 100, 2),
            away_win_rate=round(away_rate * 100, 2),
            position=dataset.position,
            points=dataset.points,
        )

    def analyze(self, fixture: MatchFixture, context: Optional[MatchContext] = None) -> FeatureAnalysis:
        context = context or MatchContext()
        try:
            is_real_source = fixture.source in {"football-data", "thesportsdb", "openligadb"}
            home_data, away_data = self.api.datasets(fixture) if is_real_source else self.mock.datasets(fixture)
            source_labels = {
                "football-data": "Football-Data API",
                "thesportsdb": "TheSportsDB free API",
                "openligadb": "OpenLigaDB free API",
            }
            source = f"{source_labels.get(fixture.source, 'deterministic mock')} + quantitative proxies"
        except FootballDataError:
            home_data, away_data = self.mock.datasets(fixture)
            source = "deterministic mock fallback + quantitative proxies"
        total_teams = max(8, len(home_data.standings_by_team_id))
        home_motivation = context.home_motivation if context.motivation_known else self._derived_motivation(home_data.position, total_teams)
        away_motivation = context.away_motivation if context.motivation_known else self._derived_motivation(away_data.position, total_teams)
        home = self._profile(home_data, fixture, True, home_motivation, context.home_travel_km)
        away = self._profile(away_data, fixture, False, away_motivation, context.away_travel_km)
        gap = round(home.power_score - away.power_score, 2)
        threshold = self.config.trend_threshold
        tendency = "home" if gap >= threshold else "away" if gap <= -threshold else "even"
        return FeatureAnalysis(
            home=home,
            away=away,
            home_power_score=home.power_score,
            away_power_score=away.power_score,
            strength_gap=gap,
            match_tendency=tendency,
            source=source,
            explanations=[
                f"Elo-like: {home.team_name} {home.elo_like_rating:.0f} vs {away.team_name} {away.elo_like_rating:.0f}",
                f"Recent-10 form: {home.recent_form_score:.1f} vs {away.recent_form_score:.1f}",
                f"Attack/defense: {home.attack_strength:.1f}/{home.defense_strength:.1f} vs {away.attack_strength:.1f}/{away.defense_strength:.1f}",
                f"Fatigue/travel: {home.fatigue_index:.1f}/{home.travel_penalty:.1f} vs {away.fatigue_index:.1f}/{away.travel_penalty:.1f}",
                "Elo、xG 与强弱对手修正均为计算代理，不是官方评级或事件级 xG。",
            ],
        )
