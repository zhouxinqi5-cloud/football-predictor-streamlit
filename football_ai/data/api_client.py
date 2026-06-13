"""Backward-compatible facade for all supported football data providers."""

from __future__ import annotations

from datetime import date
from typing import Iterable, List, Optional, Tuple

from football_ai.config import MatchFixture, TeamDataset
from football_ai.data.football_data_client import FootballDataClient
from football_ai.data.openligadb_client import OpenLigaDBClient
from football_ai.data.thesportsdb_client import TheSportsDBClient
from football_predictor.data_fetcher import FootballDataError


class ApiClient:
    def __init__(self, api_key: Optional[str] = None, timezone_name: str = "Asia/Shanghai") -> None:
        self.football_data = FootballDataClient(api_key=api_key, timezone_name=timezone_name)
        self.thesportsdb = TheSportsDBClient(timezone_name=timezone_name)
        self.openligadb = OpenLigaDBClient(timezone_name=timezone_name)

    @property
    def available(self) -> bool:
        return self.football_data.available

    def fixtures(self, target_date: date, competition_codes: Iterable[str]) -> List[MatchFixture]:
        return self.football_data.get_matches_by_date(target_date, competition_codes)

    def datasets(self, fixture: MatchFixture) -> Tuple[TeamDataset, TeamDataset]:
        providers = {
            "football-data": self.football_data,
            "thesportsdb": self.thesportsdb,
            "openligadb": self.openligadb,
        }
        provider = providers.get(fixture.source)
        if provider is None:
            raise FootballDataError(f"数据来源 {fixture.source} 不支持自动基本面")
        return provider.datasets(fixture)
