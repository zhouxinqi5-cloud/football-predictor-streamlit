"""Shared contracts and tunable parameters for the professional engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class EngineWeights:
    fundamentals: float = 0.50
    odds: float = 0.25
    market_behavior: float = 0.25

    def __post_init__(self) -> None:
        if abs(self.fundamentals + self.odds + self.market_behavior - 1.0) > 1e-9:
            raise ValueError("融合权重之和必须等于 1")


@dataclass(frozen=True)
class FeatureWeights:
    elo: float = 0.22
    recent_form: float = 0.18
    attack: float = 0.16
    defense: float = 0.16
    venue: float = 0.09
    freshness: float = 0.08
    motivation: float = 0.08
    travel: float = 0.03

    def __post_init__(self) -> None:
        if abs(sum(self.__dict__.values()) - 1.0) > 1e-9:
            raise ValueError("基本面权重之和必须等于 1")


@dataclass(frozen=True)
class EngineConfig:
    weights: EngineWeights = field(default_factory=EngineWeights)
    feature_weights: FeatureWeights = field(default_factory=FeatureWeights)
    trend_threshold: float = 5.0
    score_max_goals: int = 6
    score_candidates: int = 6
    conservative_shrinkage: float = 0.06
    conflict_shrinkage: float = 0.08
    trap_shrinkage: float = 0.08


ENGINE_CONFIG = EngineConfig()


@dataclass(frozen=True)
class MatchFixture:
    match_id: str
    home_team: str
    away_team: str
    league: str
    competition_code: str
    kickoff_time: datetime
    neutral_ground: bool
    source: str
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    home_position: Optional[int] = None
    away_position: Optional[int] = None

    @property
    def label(self) -> str:
        source = "API" if self.source == "football-data" else "MOCK"
        return (
            f"{self.kickoff_time:%H:%M}｜{self.league}｜"
            f"{self.home_team} vs {self.away_team}｜{source}"
        )


@dataclass(frozen=True)
class TeamMotivation:
    title_race_pressure: float = 50.0
    relegation_pressure: float = 50.0
    qualification_pressure: float = 50.0
    certainty: float = 55.0

    def __post_init__(self) -> None:
        for value in self.__dict__.values():
            if not 0 <= value <= 100:
                raise ValueError("动机指数必须在 0 到 100 之间")


@dataclass(frozen=True)
class MatchContext:
    home_motivation: TeamMotivation = field(default_factory=TeamMotivation)
    away_motivation: TeamMotivation = field(default_factory=TeamMotivation)
    home_travel_km: float = 0.0
    away_travel_km: float = 0.0
    motivation_known: bool = False
    final_group_round: bool = False
    knockout_match: bool = False


@dataclass(frozen=True)
class EuropeanOdds:
    home: float
    draw: float
    away: float

    def __post_init__(self) -> None:
        if min(self.home, self.draw, self.away) <= 1.0:
            raise ValueError("欧赔必须大于 1")


@dataclass(frozen=True)
class AsianOdds:
    handicap: float
    home_water: float
    away_water: float

    def __post_init__(self) -> None:
        if min(self.home_water, self.away_water) <= 0:
            raise ValueError("亚盘水位必须大于 0")


@dataclass(frozen=True)
class TotalsOdds:
    line: float
    over_water: float
    under_water: float

    def __post_init__(self) -> None:
        if self.line < 0 or min(self.over_water, self.under_water) <= 0:
            raise ValueError("大小球输入无效")


@dataclass(frozen=True)
class OddsInput:
    european_opening: EuropeanOdds = field(default_factory=lambda: EuropeanOdds(2.10, 3.30, 3.50))
    european_current: EuropeanOdds = field(default_factory=lambda: EuropeanOdds(2.05, 3.35, 3.65))
    asian_opening: AsianOdds = field(default_factory=lambda: AsianOdds(-0.25, 0.92, 0.94))
    asian_current: AsianOdds = field(default_factory=lambda: AsianOdds(-0.25, 0.88, 0.98))
    totals_opening: TotalsOdds = field(default_factory=lambda: TotalsOdds(2.50, 0.92, 0.94))
    totals_current: TotalsOdds = field(default_factory=lambda: TotalsOdds(2.50, 0.88, 0.98))
    source: str = "manual"


@dataclass(frozen=True)
class TeamDataset:
    team_id: int
    team_name: str
    position: Optional[int]
    points: Optional[int]
    played_games: Optional[int]
    goals_for: Optional[int]
    goals_against: Optional[int]
    matches: List[Dict]
    standings_by_team_id: Dict[int, Dict]
    source: str
