"""系统使用的核心数据结构与分析结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple


def _validate_rating(name: str, value: float) -> None:
    if not 0 <= value <= 100:
        raise ValueError(f"{name} 必须在 0 到 100 之间")


class MatchType(str, Enum):
    GROUP = "小组赛"
    KNOCKOUT = "淘汰赛"
    LEAGUE = "联赛"
    FRIENDLY = "友谊赛"


@dataclass(frozen=True)
class InjuryInfo:
    player: str
    status: str
    impact: float
    note: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.impact <= 10:
            raise ValueError("伤停影响值必须在 0 到 10 之间")


@dataclass(frozen=True)
class VenuePerformance:
    home_rating: float
    away_rating: float
    neutral_rating: float = 50.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _validate_rating(name, value)


@dataclass(frozen=True)
class TeamInfo:
    name: str
    strength_rating: float
    recent_results: List[str]
    attack_rating: float
    defense_rating: float
    key_player_status: str
    key_player_availability: float
    injuries: List[InjuryInfo]
    venue_performance: VenuePerformance
    fitness_rating: float
    tactical_style: str
    schedule_density: float = 50.0
    weather_adaptability: float = 50.0
    pitch_adaptability: float = 50.0
    injury_information_complete: bool = True

    def __post_init__(self) -> None:
        ratings = {
            "实力评级": self.strength_rating,
            "进攻能力": self.attack_rating,
            "防守能力": self.defense_rating,
            "关键球员可用度": self.key_player_availability,
            "体能": self.fitness_rating,
            "赛程密度": self.schedule_density,
            "天气适应性": self.weather_adaptability,
            "场地适应性": self.pitch_adaptability,
        }
        for name, value in ratings.items():
            _validate_rating(name, value)


@dataclass(frozen=True)
class HeadToHead:
    home_wins: int
    draws: int
    away_wins: int
    description: str = ""

    @property
    def total(self) -> int:
        return self.home_wins + self.draws + self.away_wins


@dataclass(frozen=True)
class MatchInfo:
    home_team: TeamInfo
    away_team: TeamInfo
    kickoff_time: datetime
    match_type: MatchType
    neutral_venue: bool
    weather: str
    venue: str
    travel_distance_km: float
    standings_context: str
    qualification_context: str
    motivation_description: str
    home_motivation: float
    away_motivation: float
    motivation_certainty: float = 70.0
    head_to_head: HeadToHead = field(default_factory=lambda: HeadToHead(0, 0, 0, "暂无交锋样本"))
    is_final_group_round: bool = False

    def __post_init__(self) -> None:
        for name, value in {
            "主队战意": self.home_motivation,
            "客队战意": self.away_motivation,
            "战意确定性": self.motivation_certainty,
        }.items():
            _validate_rating(name, value)
        if self.travel_distance_km < 0:
            raise ValueError("旅行距离不能为负数")


@dataclass(frozen=True)
class EuropeanOdds:
    home_win: float
    draw: float
    away_win: float

    def __post_init__(self) -> None:
        if min(self.home_win, self.draw, self.away_win) <= 1.0:
            raise ValueError("欧赔十进制赔率必须大于 1")


@dataclass(frozen=True)
class AsianHandicapOdds:
    handicap: float
    upper_water: float
    lower_water: float

    def __post_init__(self) -> None:
        if min(self.upper_water, self.lower_water) <= 0:
            raise ValueError("亚盘水位必须大于 0")


@dataclass(frozen=True)
class TotalsOdds:
    line: float
    over_water: float
    under_water: float

    def __post_init__(self) -> None:
        if self.line < 0 or min(self.over_water, self.under_water) <= 0:
            raise ValueError("大小球盘口或水位无效")


@dataclass(frozen=True)
class OddsData:
    european_opening: EuropeanOdds
    european_current: EuropeanOdds
    asian_opening: AsianHandicapOdds
    asian_current: AsianHandicapOdds
    totals_opening: TotalsOdds
    totals_current: TotalsOdds
    bookmaker: str
    updated_at: datetime


@dataclass
class FundamentalAnalysis:
    home_score: float
    away_score: float
    tendency: str
    reasons: List[str]
    components: Dict[str, Tuple[float, float]]


@dataclass
class EuropeanOddsAnalysis:
    opening_probabilities: Dict[str, float]
    current_probabilities: Dict[str, float]
    odds_movements: Dict[str, float]
    probability_movements: Dict[str, float]
    opening_return_rate: float
    current_return_rate: float
    simplified_kelly: Dict[str, float]
    tendency: str
    explanations: List[str]


@dataclass
class AsianOddsAnalysis:
    opening_reasonable: bool
    expected_handicap: float
    handicap_movement: str
    water_movement: str
    movement_pattern: str
    insufficient_concession: bool
    home_bias: float
    tendency: str
    risk_notes: List[str]


@dataclass
class TotalsAnalysis:
    opening_expected_goals: float
    current_expected_goals: float
    line_movement: str
    over_water_movement: float
    under_water_movement: float
    over_bias: float
    tendency: str
    explanations: List[str]


@dataclass
class OddsAnalysis:
    european: EuropeanOddsAnalysis
    asian: AsianOddsAnalysis
    totals: TotalsAnalysis


@dataclass
class MarketDiagnostics:
    fundamental_side: str
    european_side: str
    asian_side: str
    fundamental_market_alignment: str
    european_asian_alignment: str
    hot_direction: str
    is_hot: bool
    conflict_count: int
    conservative_shrinkage: float
    notes: List[str]


@dataclass
class ProbabilityPrediction:
    home_win: float
    draw: float
    away_win: float
    component_probabilities: Dict[str, Dict[str, float]]
    component_weights: Dict[str, float]
    diagnostics: MarketDiagnostics


@dataclass
class ScoreCandidate:
    score: str
    estimated_probability: float
    probability_range: str


@dataclass
class ScorePrediction:
    home_expected_goals: float
    away_expected_goals: float
    candidates: List[ScoreCandidate]
    goal_ranges: Dict[str, float]


@dataclass
class RiskAnalysis:
    level: str
    score: float
    factors: List[str]
    warnings: List[str]
