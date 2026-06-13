"""Automatic match loader with API-first and deterministic mock fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

from football_ai.config import MatchFixture
from football_ai.data.football_data_client import FootballDataClient
from football_ai.data.mock_data import MockDataProvider
from football_ai.data.openligadb_client import OpenLigaDBClient
from football_ai.data.thesportsdb_client import TheSportsDBClient
from football_predictor.data_fetcher import FootballDataError


@dataclass(frozen=True)
class MatchLoadResult:
    fixtures: List[MatchFixture]
    target_date: date
    source: str
    api_configured: bool
    fallback_reason: Optional[str] = None
    failures: tuple[str, ...] = ()

    @property
    def is_real_data(self) -> bool:
        return self.source in {"football-data", "thesportsdb", "openligadb"}


class MatchLoader:
    def __init__(self, api_key: Optional[str] = None, enable_fallback_apis: bool = True) -> None:
        self.football_data = FootballDataClient(api_key=api_key)
        self.thesportsdb = TheSportsDBClient()
        self.openligadb = OpenLigaDBClient()
        self.mock = MockDataProvider()
        self.enable_fallback_apis = enable_fallback_apis

    def load(
        self,
        target_date: Optional[date] = None,
        competition_codes: Optional[Iterable[str]] = None,
    ) -> List[MatchFixture]:
        return self.load_with_status(target_date, competition_codes).fixtures

    def load_with_status(
        self,
        target_date: Optional[date] = None,
        competition_codes: Optional[Iterable[str]] = None,
    ) -> MatchLoadResult:
        target = target_date or date.today()
        codes = tuple(competition_codes or ("PL", "PD", "BL1", "SA", "FL1"))
        failures: List[str] = []
        if self.football_data.available:
            try:
                return MatchLoadResult(
                    fixtures=self.football_data.get_matches_by_date(target, codes),
                    target_date=target,
                    source="football-data",
                    api_configured=True,
                )
            except FootballDataError as exc:
                failures.append(f"Football-Data: {exc}")
        else:
            failures.append("Football-Data: 未配置 FOOTBALL_DATA_API_KEY")
        if self.enable_fallback_apis:
            try:
                return MatchLoadResult(
                    fixtures=self.thesportsdb.get_matches_by_date(target, codes),
                    target_date=target,
                    source="thesportsdb",
                    api_configured=self.football_data.available,
                    failures=tuple(failures),
                )
            except FootballDataError as exc:
                failures.append(f"TheSportsDB: {exc}")
            try:
                return MatchLoadResult(
                    fixtures=self.openligadb.get_matches_by_date(target, codes),
                    target_date=target,
                    source="openligadb",
                    api_configured=self.football_data.available,
                    failures=tuple(failures),
                )
            except FootballDataError as exc:
                failures.append(f"OpenLigaDB: {exc}")
        else:
            failures.append("备用真实 API：当前环境已禁用外部请求")
        return MatchLoadResult(
            fixtures=self.mock.fixtures(target, codes),
            target_date=target,
            source="mock",
            api_configured=self.football_data.available,
            fallback_reason="；".join(failures),
            failures=tuple(failures),
        )
