"""Automatic match loader with API-first and deterministic mock fallback."""

from __future__ import annotations

from datetime import date
from typing import Iterable, List, Optional

from football_ai.config import MatchFixture
from football_ai.data.api_client import ApiClient
from football_ai.data.mock_data import MockDataProvider
from football_predictor.data_fetcher import FootballDataError


class MatchLoader:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api = ApiClient(api_key=api_key)
        self.mock = MockDataProvider()

    def load(
        self,
        target_date: Optional[date] = None,
        competition_codes: Optional[Iterable[str]] = None,
    ) -> List[MatchFixture]:
        target = target_date or date.today()
        codes = tuple(competition_codes or ("PL", "PD", "BL1", "SA", "FL1"))
        if self.api.available:
            try:
                return self.api.fixtures(target, codes)
            except FootballDataError:
                pass
        return self.mock.fixtures(target, codes)
