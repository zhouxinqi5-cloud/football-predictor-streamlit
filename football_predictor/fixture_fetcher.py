"""自动赛程获取：Football-Data 优先，无 Key 或失败时使用稳定 mock 数据。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Iterable, List, Optional
from zoneinfo import ZoneInfo

from .data_fetcher import FootballDataError, FootballDataFetcher


COMPETITIONS = {
    "WC": "世界杯",
    "PL": "英超",
    "PD": "西甲",
    "BL1": "德甲",
    "SA": "意甲",
    "FL1": "法甲",
    "CL": "欧冠",
}


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    home_team: str
    away_team: str
    kickoff_time: datetime
    competition_code: str
    competition_name: str
    neutral_venue: bool
    source: str
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    home_position: Optional[int] = None
    away_position: Optional[int] = None

    @property
    def display_name(self) -> str:
        source = "模拟" if self.source == "mock" else "API"
        return (
            f"{self.kickoff_time:%H:%M}｜{self.competition_name}｜"
            f"{self.home_team} vs {self.away_team}｜{source}"
        )


class FixtureFetcher:
    def __init__(
        self,
        api_key: Optional[str] = None,
        timezone_name: str = "Asia/Shanghai",
        data_fetcher: Optional[FootballDataFetcher] = None,
    ) -> None:
        self.data_fetcher = data_fetcher or FootballDataFetcher(api_key=api_key, min_request_interval=0.12)
        self.timezone = ZoneInfo(timezone_name)

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    def _from_api(self, target_date: date, codes: Iterable[str]) -> List[Fixture]:
        fixtures: List[Fixture] = []
        errors: List[str] = []
        for raw_code in codes:
            code = raw_code.upper()
            try:
                matches = self.data_fetcher.get_fixtures(code, target_date, target_date)
                try:
                    table = self.data_fetcher.get_standings(code)
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
            for match in matches:
                home = match.get("homeTeam", {})
                away = match.get("awayTeam", {})
                if not home.get("name") or not away.get("name") or not match.get("utcDate"):
                    continue
                kickoff = self._parse_utc(match["utcDate"]).astimezone(self.timezone)
                fixtures.append(
                    Fixture(
                        fixture_id=str(match.get("id", f"{code}-{home.get('id')}-{away.get('id')}")),
                        home_team=home["name"],
                        away_team=away["name"],
                        kickoff_time=kickoff,
                        competition_code=code,
                        competition_name=match.get("competition", {}).get("name") or COMPETITIONS.get(code, code),
                        neutral_venue=code == "WC",
                        source="football-data",
                        home_team_id=home.get("id"),
                        away_team_id=away.get("id"),
                        home_position=positions.get(home.get("id")),
                        away_position=positions.get(away.get("id")),
                    )
                )
        if fixtures:
            return sorted(fixtures, key=lambda item: item.kickoff_time)
        detail = "；".join(errors) if errors else "所选赛事当日无比赛"
        raise FootballDataError(detail)

    @staticmethod
    def _mock_schedule() -> dict[str, list[tuple[str, str]]]:
        return {
            "PL": [("Arsenal FC", "Chelsea FC"), ("Liverpool FC", "Newcastle United FC")],
            "PD": [("Real Madrid CF", "Villarreal CF"), ("FC Barcelona", "Sevilla FC")],
            "BL1": [("FC Bayern München", "RB Leipzig"), ("Bayer 04 Leverkusen", "Eintracht Frankfurt")],
            "SA": [("FC Internazionale Milano", "AS Roma"), ("Juventus FC", "Atalanta BC")],
            "FL1": [("Paris Saint-Germain FC", "Olympique Lyonnais"), ("AS Monaco FC", "Lille OSC")],
            "CL": [("Manchester City FC", "Real Madrid CF"), ("FC Bayern München", "Paris Saint-Germain FC")],
            "WC": [("Brazil", "Morocco"), ("Argentina", "France")],
        }

    def _mock(self, target_date: date, codes: Iterable[str]) -> List[Fixture]:
        fixtures: List[Fixture] = []
        schedule = self._mock_schedule()
        for code_index, raw_code in enumerate(codes):
            code = raw_code.upper()
            pairs = schedule.get(code, [(f"{code} Home", f"{code} Away")])
            for pair_index, (home, away) in enumerate(pairs):
                digest = hashlib.sha256(f"{target_date}:{code}:{home}:{away}".encode()).digest()
                hour = 18 + (digest[0] % 5)
                minute = 30 if digest[1] % 2 else 0
                kickoff = datetime.combine(target_date, time(hour, minute), tzinfo=self.timezone)
                fixtures.append(
                    Fixture(
                        fixture_id=f"mock-{target_date}-{code}-{pair_index}",
                        home_team=home,
                        away_team=away,
                        kickoff_time=kickoff,
                        competition_code=code,
                        competition_name=COMPETITIONS.get(code, code),
                        neutral_venue=code == "WC",
                        source="mock",
                        home_position=1 + digest[2] % 18,
                        away_position=1 + digest[3] % 18,
                    )
                )
        return sorted(fixtures, key=lambda item: item.kickoff_time)

    def fetch(
        self,
        target_date: Optional[date] = None,
        competition_codes: Optional[Iterable[str]] = None,
    ) -> List[Fixture]:
        target = target_date or date.today()
        codes = list(competition_codes or ("PL", "PD", "BL1", "SA", "FL1"))
        if self.data_fetcher.available:
            try:
                return self._from_api(target, codes)
            except FootballDataError:
                pass
        return self._mock(target, codes)
