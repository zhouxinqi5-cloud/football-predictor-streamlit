"""Football-Data.org v4 免费数据客户端。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests


class FootballDataError(RuntimeError):
    """Football-Data 请求或数据解析错误。"""


@dataclass(frozen=True)
class TeamFundamentalData:
    team_id: int
    team_name: str
    position: Optional[int]
    points: Optional[int]
    played_games: Optional[int]
    wins: Optional[int]
    draws: Optional[int]
    losses: Optional[int]
    table_goals_for: Optional[int]
    table_goals_against: Optional[int]
    recent_results: List[str]
    recent_goals_for: int
    recent_goals_against: int
    recent_matches_count: int
    attack_rating: float
    defense_rating: float
    strength_rating: float

    @property
    def recent_form_text(self) -> str:
        return " ".join(self.recent_results) if self.recent_results else "暂无数据"

    @property
    def standing_text(self) -> str:
        if self.position is None:
            return "积分榜暂无该队数据"
        return (
            f"第 {self.position} 名，{self.points} 分，赛 {self.played_games} 场，"
            f"{self.wins}胜 {self.draws}平 {self.losses}负，"
            f"进 {self.table_goals_for} 球 / 失 {self.table_goals_against} 球"
        )


@dataclass(frozen=True)
class MatchFundamentalData:
    competition_code: str
    home: TeamFundamentalData
    away: TeamFundamentalData
    matching_fixture: Optional[Dict[str, Any]]


class FootballDataFetcher:
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 12.0,
        session: Optional[requests.Session] = None,
        min_request_interval: float = 0.0,
    ) -> None:
        self.api_key = (api_key or os.getenv("FOOTBALL_DATA_API_KEY", "")).strip()
        self.timeout = timeout
        self.session = session or requests.Session()
        self.min_request_interval = max(0.0, min_request_interval)
        self._last_request_at = 0.0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise FootballDataError(
                "未配置 FOOTBALL_DATA_API_KEY。请配置后重试，或继续手动输入基本面数据。"
            )

        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        try:
            response = self.session.get(
                url,
                headers={"X-Auth-Token": self.api_key},
                params=params or {},
                timeout=self.timeout,
            )
            self._last_request_at = time.monotonic()
            response.raise_for_status()
        except requests.Timeout as exc:
            raise FootballDataError("Football-Data 请求超时，请稍后重试。") from exc
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            if status == 401:
                message = "Football-Data API Key 无效或未授权。"
            elif status == 403:
                message = "当前免费套餐无权访问该赛事或资源。"
            elif status == 429:
                message = "Football-Data 请求过于频繁，已触发限流，请稍后重试。"
            else:
                message = f"Football-Data 请求失败：{exc}"
            raise FootballDataError(message) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise FootballDataError("Football-Data 返回了无法解析的数据。") from exc
        if not isinstance(payload, dict):
            raise FootballDataError("Football-Data 返回格式异常。")
        return payload

    def get_fixtures(
        self,
        competition_code: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {}
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            # Football-Data v4 的 dateTo 为排他边界，这里对调用方提供包含结束日的语义。
            params["dateTo"] = (date_to + timedelta(days=1)).isoformat()
        payload = self._request(f"competitions/{competition_code}/matches", params)
        return list(payload.get("matches", []))

    def get_standings(self, competition_code: str) -> List[Dict[str, Any]]:
        payload = self._request(f"competitions/{competition_code}/standings")
        standings = payload.get("standings", [])
        for group in standings:
            if group.get("type") == "TOTAL":
                return list(group.get("table", []))
        return list(standings[0].get("table", [])) if standings else []

    def get_competition_teams(self, competition_code: str) -> List[Dict[str, Any]]:
        payload = self._request(f"competitions/{competition_code}/teams")
        return list(payload.get("teams", []))

    def get_recent_matches(self, team_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        payload = self._request(
            f"teams/{team_id}/matches",
            {"status": "FINISHED", "limit": str(max(1, min(limit, 20)))},
        )
        matches = list(payload.get("matches", []))
        matches.sort(key=lambda match: match.get("utcDate", ""), reverse=True)
        return matches[:limit]

    @staticmethod
    def _normalize_name(name: str) -> str:
        return "".join(character.lower() for character in name if character.isalnum())

    def _find_team(self, teams: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        normalized_query = self._normalize_name(query)
        exact = []
        partial = []
        for team in teams:
            names = [team.get("name", ""), team.get("shortName", ""), team.get("tla", "")]
            normalized_names = [self._normalize_name(name) for name in names if name]
            if normalized_query in normalized_names:
                exact.append(team)
            elif any(normalized_query in name or name in normalized_query for name in normalized_names):
                partial.append(team)
        matches = exact or partial
        if not matches:
            raise FootballDataError(f"在该赛事中未找到球队“{query}”，建议使用 API 官方英文名称。")
        if len(matches) > 1:
            candidates = "、".join(team.get("name", "未知") for team in matches[:5])
            raise FootballDataError(f"球队名称“{query}”匹配到多个结果：{candidates}。请输入更完整名称。")
        return matches[0]

    @staticmethod
    def _result_for_team(match: Dict[str, Any], team_id: int) -> tuple[str, int, int]:
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        full_time = match.get("score", {}).get("fullTime", {})
        home_goals = full_time.get("home")
        away_goals = full_time.get("away")
        if home_goals is None or away_goals is None:
            return "平", 0, 0
        is_home = home.get("id") == team_id
        goals_for, goals_against = (home_goals, away_goals) if is_home else (away_goals, home_goals)
        result = "胜" if goals_for > goals_against else "负" if goals_for < goals_against else "平"
        return result, int(goals_for), int(goals_against)

    @staticmethod
    def _clamp(value: float, low: float = 30.0, high: float = 95.0) -> float:
        return max(low, min(high, value))

    def _build_team_summary(
        self,
        team: Dict[str, Any],
        table: List[Dict[str, Any]],
        matches: List[Dict[str, Any]],
    ) -> TeamFundamentalData:
        team_id = int(team["id"])
        row = next((item for item in table if item.get("team", {}).get("id") == team_id), {})
        results: List[str] = []
        goals_for = 0
        goals_against = 0
        for match in matches:
            result, scored, conceded = self._result_for_team(match, team_id)
            results.append(result)
            goals_for += scored
            goals_against += conceded

        count = len(matches)
        average_for = goals_for / count if count else 1.2
        average_against = goals_against / count if count else 1.2
        attack_rating = self._clamp(48 + average_for * 19)
        defense_rating = self._clamp(92 - average_against * 24)

        played = row.get("playedGames")
        points = row.get("points")
        ppg = points / played if played else 1.3
        position = row.get("position")
        position_bonus = max(-8.0, 10.0 - (position or 10) * 1.2)
        strength_rating = self._clamp(48 + ppg * 15 + position_bonus)
        return TeamFundamentalData(
            team_id=team_id,
            team_name=team.get("name", "未知球队"),
            position=position,
            points=points,
            played_games=played,
            wins=row.get("won"),
            draws=row.get("draw"),
            losses=row.get("lost"),
            table_goals_for=row.get("goalsFor"),
            table_goals_against=row.get("goalsAgainst"),
            recent_results=results,
            recent_goals_for=goals_for,
            recent_goals_against=goals_against,
            recent_matches_count=count,
            attack_rating=round(attack_rating, 1),
            defense_rating=round(defense_rating, 1),
            strength_rating=round(strength_rating, 1),
        )

    def get_match_fundamentals(
        self,
        competition_code: str,
        home_team_name: str,
        away_team_name: str,
        match_date: Optional[date] = None,
    ) -> MatchFundamentalData:
        code = competition_code.strip().upper()
        teams = self.get_competition_teams(code)
        home_team = self._find_team(teams, home_team_name)
        away_team = self._find_team(teams, away_team_name)
        table = self.get_standings(code)
        home_matches = self.get_recent_matches(int(home_team["id"]), 5)
        away_matches = self.get_recent_matches(int(away_team["id"]), 5)

        fixture = None
        if match_date:
            fixtures = self.get_fixtures(code, match_date, match_date)
            fixture = next(
                (
                    item
                    for item in fixtures
                    if item.get("homeTeam", {}).get("id") == home_team.get("id")
                    and item.get("awayTeam", {}).get("id") == away_team.get("id")
                ),
                None,
            )
        return MatchFundamentalData(
            competition_code=code,
            home=self._build_team_summary(home_team, table, home_matches),
            away=self._build_team_summary(away_team, table, away_matches),
            matching_fixture=fixture,
        )
