"""Football-Data API adapter with no scraping and explicit failure behavior."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from football_ai.config import MatchFixture, TeamDataset
from football_predictor.data_fetcher import FootballDataError, FootballDataFetcher


class ApiClient:
    def __init__(self, api_key: Optional[str] = None, timezone_name: str = "Asia/Shanghai") -> None:
        self.fetcher = FootballDataFetcher(api_key=api_key, min_request_interval=0.15)
        self.timezone = ZoneInfo(timezone_name)

    @property
    def available(self) -> bool:
        return self.fetcher.available

    def fixtures(self, target_date: date, competition_codes: Iterable[str]) -> List[MatchFixture]:
        if not self.available:
            raise FootballDataError("Football-Data API Key 未配置")
        output: List[MatchFixture] = []
        errors = []
        for code in competition_codes:
            code = code.upper()
            try:
                matches = self.fetcher.get_fixtures(code, target_date, target_date)
                try:
                    table = self.fetcher.get_standings(code)
                except FootballDataError:
                    table = []
            except FootballDataError as exc:
                errors.append(str(exc))
                continue
            positions = {
                row.get("team", {}).get("id"): row.get("position")
                for row in table
                if row.get("team", {}).get("id") is not None
            }
            for match in matches:
                home = match.get("homeTeam", {})
                away = match.get("awayTeam", {})
                if not home.get("name") or not away.get("name") or not match.get("utcDate"):
                    continue
                local_time = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")).astimezone(self.timezone)
                output.append(
                    MatchFixture(
                        match_id=str(match.get("id")),
                        home_team=home["name"],
                        away_team=away["name"],
                        league=match.get("competition", {}).get("name") or code,
                        competition_code=code,
                        kickoff_time=local_time,
                        neutral_ground=code == "WC",
                        source="football-data",
                        home_team_id=home.get("id"),
                        away_team_id=away.get("id"),
                        home_position=positions.get(home.get("id")),
                        away_position=positions.get(away.get("id")),
                    )
                )
        if not output:
            raise FootballDataError("；".join(errors) if errors else "所选日期无可用比赛")
        return sorted(output, key=lambda item: item.kickoff_time)

    def datasets(self, fixture: MatchFixture) -> Tuple[TeamDataset, TeamDataset]:
        if not self.available or fixture.home_team_id is None or fixture.away_team_id is None:
            raise FootballDataError("比赛缺少可用 API 球队 ID")
        table = self.fetcher.get_standings(fixture.competition_code)
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
            matches = self.fetcher.get_recent_matches(team_id, 20)
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
                    matches=matches,
                    standings_by_team_id=standings,
                    source="football-data",
                )
            )
        return output[0], output[1]
