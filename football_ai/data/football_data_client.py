"""Football-Data.org v4 client for fixtures, schedules, tables and recent form."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from football_ai.config import MatchFixture, TeamDataset
from football_predictor.data_fetcher import FootballDataError, FootballDataFetcher


class FootballDataClient:
    source = "football-data"

    def __init__(self, api_key: Optional[str] = None, timezone_name: str = "Asia/Shanghai") -> None:
        self.fetcher = FootballDataFetcher(api_key=api_key, min_request_interval=0.15)
        self.timezone = ZoneInfo(timezone_name)

    @property
    def available(self) -> bool:
        return self.fetcher.available

    def get_matches_by_date(self, target_date: date, competition_codes: Iterable[str]) -> List[MatchFixture]:
        if not self.available:
            raise FootballDataError("Football-Data API Key 未配置")
        output: List[MatchFixture] = []
        errors: List[str] = []
        codes = tuple(code.upper() for code in competition_codes)
        if "ALL" in codes:
            params = {"dateFrom": target_date.isoformat(), "dateTo": (target_date + timedelta(days=1)).isoformat()}
            payload = self.fetcher._request("matches", params)
            matches = list(payload.get("matches", []))
            return self._parse_matches(matches, "ALL", [])
        for code in codes:
            code = code.upper()
            try:
                matches = self.get_competition_schedule(code, target_date, target_date)
                try:
                    table = self.get_standings(code)
                except FootballDataError:
                    table = []
            except FootballDataError as exc:
                errors.append(f"{code}: {exc}")
                continue
            positions = {
                row.get("team", {}).get("id"): row.get("position")
                for row in table
                if row.get("team", {}).get("id") is not None
            }
            output.extend(self._parse_matches(matches, code, positions))
        if not output:
            raise FootballDataError("；".join(errors) if errors else "所选日期和赛事无可用比赛")
        return sorted(output, key=lambda item: item.kickoff_time)

    def _parse_matches(self, matches: List[Dict], default_code: str, positions) -> List[MatchFixture]:
        output = []
        for match in matches:
            home = match.get("homeTeam", {})
            away = match.get("awayTeam", {})
            if not home.get("name") or not away.get("name") or not match.get("utcDate"):
                continue
            competition = match.get("competition", {})
            code = competition.get("code") or default_code
            kickoff = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")).astimezone(self.timezone)
            output.append(MatchFixture(
                match_id=str(match.get("id")),
                home_team=home["name"],
                away_team=away["name"],
                league=competition.get("name") or code,
                competition_code=code,
                kickoff_time=kickoff,
                neutral_ground=code == "WC",
                source=self.source,
                home_team_id=home.get("id"),
                away_team_id=away.get("id"),
                home_position=positions.get(home.get("id")) if positions else None,
                away_position=positions.get(away.get("id")) if positions else None,
            ))
        if not output:
            raise FootballDataError("Football-Data 所选日期和赛事无比赛")
        return output

    def get_competition_schedule(
        self,
        competition_code: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict]:
        return self.fetcher.get_fixtures(competition_code, date_from, date_to)

    def get_standings(self, competition_code: str) -> List[Dict]:
        return self.fetcher.get_standings(competition_code)

    def get_recent_matches(self, team_id: int, limit: int = 10) -> List[Dict]:
        return self.fetcher.get_recent_matches(team_id, limit)

    def datasets(self, fixture: MatchFixture) -> Tuple[TeamDataset, TeamDataset]:
        if not self.available or fixture.home_team_id is None or fixture.away_team_id is None:
            raise FootballDataError("比赛缺少可用 Football-Data 球队 ID")
        table = self.get_standings(fixture.competition_code)
        standings: Dict[int, Dict] = {
            row.get("team", {}).get("id"): row
            for row in table
            if row.get("team", {}).get("id") is not None
        }
        output = []
        for team_id, team_name in (
            (fixture.home_team_id, fixture.home_team),
            (fixture.away_team_id, fixture.away_team),
        ):
            row = standings.get(team_id, {})
            output.append(
                TeamDataset(
                    team_id=team_id,
                    team_name=team_name,
                    position=row.get("position"),
                    points=row.get("points"),
                    played_games=row.get("playedGames"),
                    goals_for=row.get("goalsFor"),
                    goals_against=row.get("goalsAgainst"),
                    matches=self.get_recent_matches(team_id, 20),
                    standings_by_team_id=standings,
                    source=self.source,
                )
            )
        return output[0], output[1]

    fixtures = get_matches_by_date
