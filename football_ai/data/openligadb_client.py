"""OpenLigaDB no-key fallback for supported German competitions."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from football_ai.config import MatchFixture, TeamDataset
from football_predictor.data_fetcher import FootballDataError


SUPPORTED_CODES = {"BL1": "bl1"}


class OpenLigaDBClient:
    source = "openligadb"
    BASE_URL = "https://api.openligadb.de"

    def __init__(self, timeout: float = 20.0, timezone_name: str = "Asia/Shanghai") -> None:
        self.timeout = timeout
        self.timezone = ZoneInfo(timezone_name)
        self.session = requests.Session()
        self._cache: Dict[str, object] = {}

    def _request(self, path: str):
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        if url in self._cache:
            return self._cache[url]
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise FootballDataError(f"OpenLigaDB 请求失败：{exc}") from exc
        self._cache[url] = payload
        return payload

    @staticmethod
    def _season(target: date) -> int:
        return target.year if target.month >= 7 else target.year - 1

    @staticmethod
    def _full_time_score(match: Dict) -> Tuple[Optional[int], Optional[int]]:
        results = match.get("matchResults") or []
        full_time = next((item for item in results if item.get("resultTypeID") == 2), None)
        if full_time is None and results:
            full_time = results[-1]
        if not full_time:
            return None, None
        return full_time.get("pointsTeam1"), full_time.get("pointsTeam2")

    def _parse_match(self, match: Dict, code: str) -> Optional[MatchFixture]:
        home, away = match.get("team1") or {}, match.get("team2") or {}
        if not home.get("teamName") or not away.get("teamName"):
            return None
        raw_date = match.get("matchDateTimeUTC") or match.get("matchDateTime")
        if not raw_date:
            return None
        kickoff = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        kickoff = kickoff.astimezone(self.timezone)
        return MatchFixture(
            match_id=f"oldb-{match.get('matchID')}",
            home_team=home["teamName"],
            away_team=away["teamName"],
            league="德国足球甲级联赛",
            competition_code=code,
            kickoff_time=kickoff,
            neutral_ground=False,
            source=self.source,
            home_team_id=home.get("teamId"),
            away_team_id=away.get("teamId"),
        )

    def get_competition_schedule(self, competition_code: str, season: int) -> List[Dict]:
        shortcut = SUPPORTED_CODES.get(competition_code.upper())
        if not shortcut:
            raise FootballDataError("OpenLigaDB 当前仅作为德国联赛备用")
        payload = self._request(f"getmatchdata/{shortcut}/{season}")
        return payload if isinstance(payload, list) else []

    def get_matches_by_date(self, target_date: date, competition_codes: Iterable[str]) -> List[MatchFixture]:
        output: List[MatchFixture] = []
        supported_requested = False
        codes = tuple(code.upper() for code in competition_codes)
        for code in codes:
            if code == "ALL":
                code = "BL1"
            code = code.upper()
            if code not in SUPPORTED_CODES:
                continue
            supported_requested = True
            for match in self.get_competition_schedule(code, self._season(target_date)):
                fixture = self._parse_match(match, code)
                if fixture and fixture.kickoff_time.date() == target_date:
                    output.append(fixture)
        if not supported_requested:
            raise FootballDataError("OpenLigaDB 不覆盖所选赛事")
        if not output:
            raise FootballDataError("OpenLigaDB 所选日期无比赛")
        return sorted(output, key=lambda item: item.kickoff_time)

    def get_standings(self, competition_code: str, season: int) -> List[Dict]:
        shortcut = SUPPORTED_CODES.get(competition_code.upper())
        if not shortcut:
            raise FootballDataError("OpenLigaDB 不覆盖该赛事")
        payload = self._request(f"getbltable/{shortcut}/{season}")
        return payload if isinstance(payload, list) else []

    def get_recent_matches(self, team_id: int, competition_code: str, season: int, limit: int = 10) -> List[Dict]:
        matches = self.get_competition_schedule(competition_code, season)
        relevant = [
            match for match in matches
            if match.get("matchIsFinished")
            and team_id in ((match.get("team1") or {}).get("teamId"), (match.get("team2") or {}).get("teamId"))
        ]
        relevant.sort(key=lambda item: item.get("matchDateTimeUTC") or item.get("matchDateTime") or "", reverse=True)
        return relevant[:limit]

    def _match_to_standard(self, match: Dict) -> Dict:
        home_goals, away_goals = self._full_time_score(match)
        return {
            "status": "FINISHED",
            "utcDate": match.get("matchDateTimeUTC") or match.get("matchDateTime"),
            "homeTeam": {"id": (match.get("team1") or {}).get("teamId")},
            "awayTeam": {"id": (match.get("team2") or {}).get("teamId")},
            "score": {"fullTime": {"home": home_goals, "away": away_goals}},
        }

    def datasets(self, fixture: MatchFixture) -> Tuple[TeamDataset, TeamDataset]:
        if fixture.home_team_id is None or fixture.away_team_id is None:
            raise FootballDataError("OpenLigaDB 比赛缺少球队 ID")
        season = self._season(fixture.kickoff_time.date())
        raw_table = self.get_standings(fixture.competition_code, season)
        standings: Dict[int, Dict] = {}
        for index, row in enumerate(raw_table, 1):
            team_id = row.get("teamInfoId")
            if team_id is None:
                continue
            standings[team_id] = {
                "position": index,
                "team": {"id": team_id, "name": row.get("teamName")},
                "playedGames": row.get("matches"),
                "points": row.get("points"),
                "goalsFor": row.get("goals"),
                "goalsAgainst": row.get("opponentGoals"),
            }
        output = []
        for team_id, team_name in ((fixture.home_team_id, fixture.home_team), (fixture.away_team_id, fixture.away_team)):
            row = standings.get(team_id, {})
            history = [
                self._match_to_standard(item)
                for item in self.get_recent_matches(team_id, fixture.competition_code, season, 20)
            ]
            output.append(TeamDataset(
                team_id=team_id,
                team_name=team_name,
                position=row.get("position"),
                points=row.get("points"),
                played_games=row.get("playedGames"),
                goals_for=row.get("goalsFor"),
                goals_against=row.get("goalsAgainst"),
                matches=history,
                standings_by_team_id=standings,
                source=self.source,
            ))
        return output[0], output[1]
