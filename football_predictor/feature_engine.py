"""只使用比赛、积分榜和计算结果生成可解释的自动基本面特征。"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .data_fetcher import FootballDataError, FootballDataFetcher
from .fixture_fetcher import Fixture


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class TeamFeatureScore:
    team_name: str
    recent_results: List[str]
    recent_goals_for: int
    recent_goals_against: int
    recent_form_score: float
    attack_score: float
    defense_score: float
    venue_score: float
    fatigue_index: float
    pressure_index: float
    basic_score: float
    home_win_rate: float
    away_win_rate: float
    clean_sheets: int
    matches_last_14_days: int
    standing_position: Optional[int]
    standing_points: Optional[int]


@dataclass(frozen=True)
class MatchFeatureResult:
    home: TeamFeatureScore
    away: TeamFeatureScore
    home_basic_score: float
    away_basic_score: float
    total_strength_diff: float
    basic_trend: str
    source: str
    explanation: List[str]


class FeatureEngine:
    def __init__(self, api_key: Optional[str] = None, data_fetcher: Optional[FootballDataFetcher] = None) -> None:
        self.data_fetcher = data_fetcher or FootballDataFetcher(api_key=api_key, min_request_interval=0.12)

    @staticmethod
    def _parse_match_date(match: Dict[str, Any]) -> datetime:
        value = match.get("utcDate") or "1970-01-01T00:00:00Z"
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _team_match_values(match: Dict[str, Any], team_id: int) -> tuple[bool, int, int, Optional[int]]:
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")
        if home_goals is None or away_goals is None:
            return home.get("id") == team_id, 0, 0, None
        is_home = home.get("id") == team_id
        opponent_id = away.get("id") if is_home else home.get("id")
        if is_home:
            return True, int(home_goals), int(away_goals), opponent_id
        return False, int(away_goals), int(home_goals), opponent_id

    @staticmethod
    def _pressure(position: Optional[int], total_teams: int) -> float:
        if position is None or total_teams <= 1:
            return 50.0
        percentile = (position - 1) / (total_teams - 1)
        if position <= max(4, round(total_teams * 0.2)):
            return _clamp(88 - position * 4)
        if percentile >= 0.75:
            return _clamp(62 + percentile * 35)
        return _clamp(42 + abs(percentile - 0.5) * 35)

    def _score_team(
        self,
        team_name: str,
        team_id: int,
        matches: List[Dict[str, Any]],
        standing: Dict[str, Any],
        standings_by_id: Dict[int, Dict[str, Any]],
        kickoff: datetime,
        is_match_home: bool,
        total_teams: int,
    ) -> TeamFeatureScore:
        finished = [match for match in matches if match.get("status") in {None, "FINISHED"}]
        finished.sort(key=self._parse_match_date, reverse=True)
        recent = finished[:5]
        results: List[str] = []
        goals_for = goals_against = clean_sheets = 0
        weighted_goals = weighted_matches = 0.0
        venue_games = venue_wins = 0
        home_games = home_wins = away_games = away_wins = 0
        for match in recent:
            is_home, scored, conceded, opponent_id = self._team_match_values(match, team_id)
            result = "胜" if scored > conceded else "负" if scored < conceded else "平"
            results.append(result)
            goals_for += scored
            goals_against += conceded
            clean_sheets += int(conceded == 0)
            opponent_position = standings_by_id.get(opponent_id or -1, {}).get("position")
            strong_opponent = opponent_position is not None and opponent_position <= max(4, total_teams // 3)
            weight = 1.20 if strong_opponent else 1.0
            weighted_goals += scored * weight
            weighted_matches += weight
            if is_home:
                home_games += 1
                home_wins += int(scored > conceded)
            else:
                away_games += 1
                away_wins += int(scored > conceded)
            if is_home == is_match_home:
                venue_games += 1
                venue_wins += int(scored > conceded)

        count = max(1, len(recent))
        form_points = sum(3 if result == "胜" else 1 if result == "平" else 0 for result in results)
        goal_balance = (goals_for - goals_against) / count
        recent_form = _clamp(form_points / (count * 3) * 72 + 28 + goal_balance * 8)
        average_weighted_goals = weighted_goals / weighted_matches if weighted_matches else 1.1
        attack = _clamp(38 + average_weighted_goals * 27)
        average_conceded = goals_against / count
        defense = _clamp(88 - average_conceded * 25 + clean_sheets / count * 15)
        home_rate = home_wins / home_games if home_games else 0.5
        away_rate = away_wins / away_games if away_games else 0.4
        relevant_rate = venue_wins / venue_games if venue_games else (home_rate if is_match_home else away_rate)
        venue_score = _clamp(42 + relevant_rate * 52 + (5 if is_match_home else 0))

        kickoff_utc = kickoff.astimezone(timezone.utc) if kickoff.tzinfo else kickoff.replace(tzinfo=timezone.utc)
        cutoff = kickoff_utc - timedelta(days=14)
        dense_matches = sum(1 for match in finished if cutoff <= self._parse_match_date(match) < kickoff_utc)
        fatigue = _clamp(max(0, dense_matches - 1) * 22)
        position = standing.get("position")
        pressure = self._pressure(position, total_teams)
        played = standing.get("playedGames") or 0
        points = standing.get("points") or 0
        points_per_game = points / played if played else 1.35
        table_strength = _clamp(42 + points_per_game * 18 + max(0, total_teams - (position or total_teams)) * 1.1)
        basic = (
            recent_form * 0.25
            + attack * 0.20
            + defense * 0.20
            + venue_score * 0.13
            + (100 - fatigue) * 0.10
            + table_strength * 0.09
            + pressure * 0.03
        )
        return TeamFeatureScore(
            team_name=team_name,
            recent_results=results,
            recent_goals_for=goals_for,
            recent_goals_against=goals_against,
            recent_form_score=round(recent_form, 2),
            attack_score=round(attack, 2),
            defense_score=round(defense, 2),
            venue_score=round(venue_score, 2),
            fatigue_index=round(fatigue, 2),
            pressure_index=round(pressure, 2),
            basic_score=round(basic, 2),
            home_win_rate=round(home_rate * 100, 2),
            away_win_rate=round(away_rate * 100, 2),
            clean_sheets=clean_sheets,
            matches_last_14_days=dense_matches,
            standing_position=position,
            standing_points=standing.get("points"),
        )

    @staticmethod
    def _trend(diff: float) -> str:
        return "home" if diff >= 5 else "away" if diff <= -5 else "even"

    def build(
        self,
        fixture: Fixture,
        home_matches: List[Dict[str, Any]],
        away_matches: List[Dict[str, Any]],
        table: List[Dict[str, Any]],
        source: str,
    ) -> MatchFeatureResult:
        standings = {
            row.get("team", {}).get("id"): row
            for row in table
            if row.get("team", {}).get("id") is not None
        }
        total_teams = len(table) if len(table) >= 8 else 20
        home_id = fixture.home_team_id or 1
        away_id = fixture.away_team_id or 2
        home = self._score_team(
            fixture.home_team, home_id, home_matches, standings.get(home_id, {}), standings,
            fixture.kickoff_time, True, total_teams,
        )
        away = self._score_team(
            fixture.away_team, away_id, away_matches, standings.get(away_id, {}), standings,
            fixture.kickoff_time, False, total_teams,
        )
        diff = round(home.basic_score - away.basic_score, 2)
        return MatchFeatureResult(
            home=home,
            away=away,
            home_basic_score=home.basic_score,
            away_basic_score=away.basic_score,
            total_strength_diff=diff,
            basic_trend=self._trend(diff),
            source=source,
            explanation=[
                f"近期状态：{home.team_name} {home.recent_form_score:.1f}，{away.team_name} {away.recent_form_score:.1f}",
                f"攻防评分：{home.team_name} {home.attack_score:.1f}/{home.defense_score:.1f}，"
                f"{away.team_name} {away.attack_score:.1f}/{away.defense_score:.1f}",
                f"14天赛程：{home.team_name} {home.matches_last_14_days} 场，{away.team_name} {away.matches_last_14_days} 场",
                f"积分压力：{home.team_name} {home.pressure_index:.1f}，{away.team_name} {away.pressure_index:.1f}",
            ],
        )

    @staticmethod
    def _mock_data(fixture: Fixture) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        seed = int(hashlib.sha256(fixture.fixture_id.encode()).hexdigest()[:16], 16)
        randomizer = random.Random(seed)
        home_id, away_id = 1, 2
        table = []
        for team_id, name, hinted_position in (
            (home_id, fixture.home_team, fixture.home_position),
            (away_id, fixture.away_team, fixture.away_position),
        ):
            position = hinted_position or randomizer.randint(1, 18)
            played = randomizer.randint(18, 30)
            points = max(8, int((2.25 - position / 18) * played * 0.72))
            table.append({
                "position": position,
                "team": {"id": team_id, "name": name},
                "playedGames": played,
                "points": points,
            })

        def matches_for(team_id: int, opponent_id: int) -> List[Dict[str, Any]]:
            matches = []
            days_ago = 2
            for index in range(12):
                is_home = index % 2 == 0
                scored = randomizer.randint(0, 3)
                conceded = randomizer.randint(0, 3)
                match_date = fixture.kickoff_time - timedelta(days=days_ago)
                days_ago += randomizer.randint(2, 6)
                matches.append({
                    "status": "FINISHED",
                    "utcDate": match_date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "homeTeam": {"id": team_id if is_home else opponent_id},
                    "awayTeam": {"id": opponent_id if is_home else team_id},
                    "score": {"fullTime": {
                        "home": scored if is_home else conceded,
                        "away": conceded if is_home else scored,
                    }},
                })
            return matches

        return matches_for(home_id, 101), matches_for(away_id, 102), table

    def build_for_fixture(self, fixture: Fixture) -> MatchFeatureResult:
        if self.data_fetcher.available and fixture.home_team_id and fixture.away_team_id and fixture.source != "mock":
            try:
                table = self.data_fetcher.get_standings(fixture.competition_code)
                home_matches = self.data_fetcher.get_recent_matches(fixture.home_team_id, 20)
                away_matches = self.data_fetcher.get_recent_matches(fixture.away_team_id, 20)
                return self.build(fixture, home_matches, away_matches, table, "football-data + 计算")
            except FootballDataError:
                pass
        home_matches, away_matches, table = self._mock_data(fixture)
        mock_fixture = replace(fixture, home_team_id=1, away_team_id=2)
        return self.build(mock_fixture, home_matches, away_matches, table, "mock + 计算")
