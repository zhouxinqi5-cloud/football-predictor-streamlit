"""Automatic match loader with API-first and deterministic mock fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

from football_ai.config import MatchFixture
from football_ai.data.api_client import ApiClient
from football_ai.data.mock_data import MockDataProvider
from football_predictor.data_fetcher import FootballDataError


@dataclass(frozen=True)
class MatchLoadResult:
    fixtures: List[MatchFixture]
    target_date: date
    source: str
    api_configured: bool
    fallback_reason: Optional[str] = None

    @property
    def is_real_data(self) -> bool:
        return self.source == "football-data"


class MatchLoader:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api = ApiClient(api_key=api_key)
        self.mock = MockDataProvider()

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
        if self.api.available:
            try:
                return MatchLoadResult(
                    fixtures=self.api.fixtures(target, codes),
                    target_date=target,
                    source="football-data",
                    api_configured=True,
                )
            except FootballDataError as exc:
                return MatchLoadResult(
                    fixtures=self.mock.fixtures(target, codes),
                    target_date=target,
                    source="mock",
                    api_configured=True,
                    fallback_reason=str(exc),
                )
        return MatchLoadResult(
            fixtures=self.mock.fixtures(target, codes),
            target_date=target,
            source="mock",
            api_configured=False,
            fallback_reason="未配置 FOOTBALL_DATA_API_KEY",
        )
