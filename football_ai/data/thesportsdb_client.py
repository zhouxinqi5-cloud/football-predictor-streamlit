"""TheSportsDB free API fallback for real fixtures and limited form data."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from football_ai.config import MatchFixture, TeamDataset
from football_predictor.data_fetcher import FootballDataError


LEAGUE_IDS = {
    "PL": "4328",
    "PD": "4335",
    "BL1": "4331",
    "SA": "4332",
    "FL1": "4334",
    "CL": "4480",
    "WC": "4429",
}


class TheSportsDBClient:
    source = "thesportsdb"
    BASE_URL = "https://www.thesportsdb.com/api/v1/json"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0, timezone_name: str = "Asia/Shanghai") -> None:
        # 123 is TheSportsDB's documented public free key, not a private credential.
        self.api_key = (api_key or os.getenv("THESPORTSDB_API_KEY", "") or "123").strip()
        self.timeout = timeout
        self.timezone = ZoneInfo(timezone_name)
        self.session = requests.Session()
        self._cache: Dict[str, Dict] = {}

    def _request(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Dict:
        url = f"{self.BASE_URL}/{self.api_key}/{endpoint}"
        cache_key = f"{url}:{sorted((params or {}).items())}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            response = self.session.get(url, params=params or {}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise FootballDataError(f"TheSportsDB 请求失败：{exc}") from exc
        if not isinstance(payload, dict):
            raise FootballDataError("TheSportsDB 返回格式异常")
        self._cache[cache_key] = payload
        return payload

    @staticmethod
    def _season(target: date) -> str:
        start_year = target.year if target.month >= 7 else target.year - 1
        return f"{start_year}-{start_year + 1}"

    def _parse_event(self, event: Dict, code: str) -> Optional[MatchFixture]:
        home, away = event.get("strHomeTeam"), event.get("strAwayTeam")
        if not home or not away:
            return None
        timestamp = event.get("strTimestamp")
        if timestamp:
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                kickoff = parsed.astimezone(self.timezone)
            except ValueError:
                timestamp = None
        if not timestamp:
            raw = f"{event.get('dateEvent', '1970-01-01')}T{event.get('strTime') or '00:00:00'}"
            kickoff = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            kickoff = kickoff.astimezone(self.timezone)
        event_league_id = str(event.get("idLeague") or "")
        resolved_code = next((item for item, league_id in LEAGUE_IDS.items() if league_id == event_league_id), None)
        competition_code = resolved_code or (f"TSDB-{event_league_id}" if event_league_id else code)
        return MatchFixture(
            match_id=f"tsdb-{event.get('idEvent')}",
            home_team=home,
            away_team=away,
            league=event.get("strLeague") or code,
            competition_code=competition_code,
            kickoff_time=kickoff,
            neutral_ground=competition_code == "WC",
            source=self.source,
            home_team_id=int(event["idHomeTeam"]) if event.get("idHomeTeam") else None,
            away_team_id=int(event["idAwayTeam"]) if event.get("idAwayTeam") else None,
        )

    def get_matches_by_date(self, target_date: date, competition_codes: Iterable[str]) -> List[MatchFixture]:
        output: List[MatchFixture] = []
        errors: List[str] = []
        codes = tuple(code.upper() for code in competition_codes)
        if "ALL" in codes:
            payload = self._request("eventsday.php", {"d": target_date.isoformat(), "s": "Soccer"})
            for event in payload.get("events") or []:
                fixture = self._parse_event(event, "ALL")
                if fixture and fixture.kickoff_time.date() == target_date:
                    output.append(fixture)
        for code in codes:
            if code == "ALL":
                continue
            league_id = LEAGUE_IDS.get(code.upper())
            if not league_id:
                continue
            try:
                payload = self._request(
                    "eventsday.php",
                    {"d": target_date.isoformat(), "s": "Soccer", "l": league_id},
                )
            except FootballDataError as exc:
                errors.append(str(exc))
                continue
            for event in payload.get("events") or []:
                fixture = self._parse_event(event, code.upper())
                if fixture and fixture.kickoff_time.date() == target_date:
                    output.append(fixture)
        if not output:
            raise FootballDataError("；".join(errors) if errors else "TheSportsDB 所选日期和赛事无比赛")
        unique = {fixture.match_id: fixture for fixture in output}
        return sorted(unique.values(), key=lambda item: item.kickoff_time)

    def get_competition_schedule(self, competition_code: str, target_date: Optional[date] = None) -> List[Dict]:
        league_id = LEAGUE_IDS.get(competition_code.upper())
        if not league_id:
            raise FootballDataError("TheSportsDB 不支持该赛事代码")
        if target_date:
            return self._request("eventsday.php", {"d": target_date.isoformat(), "s": "Soccer", "l": league_id}).get("events") or []
        return self._request("eventsnextleague.php", {"id": league_id}).get("events") or []

    def get_standings(self, competition_code: str, target_date: Optional[date] = None) -> List[Dict]:
        league_id = self._league_id(competition_code)
        if not league_id:
            raise FootballDataError("TheSportsDB 不支持该赛事代码")
        payload = self._request("lookuptable.php", {"l": league_id, "s": self._season(target_date or date.today())})
        return payload.get("table") or []

    @staticmethod
    def _league_id(competition_code: str) -> Optional[str]:
        code = competition_code.upper()
        if code.startswith("TSDB-"):
            return code.split("-", 1)[1]
        return LEAGUE_IDS.get(code)

    def get_recent_matches(self, team_id: int, limit: int = 10) -> List[Dict]:
        events = self._request("eventslast.php", {"id": str(team_id)}).get("results") or []
        return events[:limit]

    @staticmethod
    def _event_to_standard(event: Dict) -> Dict:
        home_score = event.get("intHomeScore")
        away_score = event.get("intAwayScore")
        timestamp = event.get("strTimestamp") or f"{event.get('dateEvent')}T{event.get('strTime') or '00:00:00'}Z"
        return {
            "status": "FINISHED",
            "utcDate": timestamp,
            "homeTeam": {"id": int(event["idHomeTeam"]) if event.get("idHomeTeam") else None},
            "awayTeam": {"id": int(event["idAwayTeam"]) if event.get("idAwayTeam") else None},
            "score": {"fullTime": {"home": int(home_score) if home_score not in (None, "") else None, "away": int(away_score) if away_score not in (None, "") else None}},
        }

    def datasets(self, fixture: MatchFixture) -> Tuple[TeamDataset, TeamDataset]:
        if fixture.home_team_id is None or fixture.away_team_id is None:
            raise FootballDataError("TheSportsDB 比赛缺少球队 ID")
        raw_table = self.get_standings(fixture.competition_code, fixture.kickoff_time.date())
        standings: Dict[int, Dict] = {}
        for index, row in enumerate(raw_table, 1):
            team_id_raw = row.get("idTeam")
            if not team_id_raw:
                continue
            team_id = int(team_id_raw)
            standings[team_id] = {
                "position": int(row.get("intRank") or index),
                "team": {"id": team_id, "name": row.get("strTeam")},
                "playedGames": int(row.get("intPlayed") or 0),
                "points": int(row.get("intPoints") or 0),
                "goalsFor": int(row.get("intGoalsFor") or 0),
                "goalsAgainst": int(row.get("intGoalsAgainst") or 0),
            }
        output = []
        for team_id, team_name in ((fixture.home_team_id, fixture.home_team), (fixture.away_team_id, fixture.away_team)):
            row = standings.get(team_id, {})
            matches = [self._event_to_standard(item) for item in self.get_recent_matches(team_id, 10)]
            output.append(TeamDataset(
                team_id=team_id,
                team_name=team_name,
                position=row.get("position"),
                points=row.get("points"),
                played_games=row.get("playedGames"),
                goals_for=row.get("goalsFor"),
                goals_against=row.get("goalsAgainst"),
                matches=matches,
                standings_by_team_id=standings,
                source=self.source,
            ))
        return output[0], output[1]
