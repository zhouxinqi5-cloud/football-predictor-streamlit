"""项目配置与可调权重。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelWeights:
    """多源概率融合权重，以基本面为主、盘口指数为辅。"""

    fundamental: float = 0.55
    european_odds: float = 0.20
    asian_handicap: float = 0.15
    totals: float = 0.10

    def __post_init__(self) -> None:
        total = self.fundamental + self.european_odds + self.asian_handicap + self.totals
        if abs(total - 1.0) > 1e-9:
            raise ValueError("概率模型权重之和必须等于 1")


@dataclass(frozen=True)
class FundamentalWeights:
    """基本面各因素权重。"""

    strength: float = 0.23
    recent_form: float = 0.15
    attack: float = 0.12
    defense: float = 0.12
    injuries: float = 0.10
    motivation: float = 0.10
    schedule: float = 0.06
    fitness: float = 0.06
    venue: float = 0.03
    head_to_head: float = 0.015
    adaptation: float = 0.015

    def __post_init__(self) -> None:
        if abs(sum(self.__dict__.values()) - 1.0) > 1e-9:
            raise ValueError("基本面权重之和必须等于 1")


@dataclass(frozen=True)
class AnalysisStyleConfig:
    """控制市场过热识别与保守概率收缩。"""

    hot_probability_threshold: float = 0.60
    hot_probability_rise_threshold: float = 0.015
    conservative_base_shrinkage: float = 0.05
    conflict_shrinkage: float = 0.07
    hot_market_shrinkage: float = 0.05
    max_conservative_shrinkage: float = 0.24

    def __post_init__(self) -> None:
        probability_fields = (
            self.hot_probability_threshold,
            self.hot_probability_rise_threshold,
            self.conservative_base_shrinkage,
            self.conflict_shrinkage,
            self.hot_market_shrinkage,
            self.max_conservative_shrinkage,
        )
        if any(not 0 <= value <= 1 for value in probability_fields):
            raise ValueError("分析风格参数必须在 0 到 1 之间")


@dataclass(frozen=True)
class PredictorConfig:
    model_weights: ModelWeights = field(default_factory=ModelWeights)
    fundamental_weights: FundamentalWeights = field(default_factory=FundamentalWeights)
    analysis_style: AnalysisStyleConfig = field(default_factory=AnalysisStyleConfig)
    tendency_threshold: float = 4.0
    score_candidate_count: int = 5
    max_score_per_team: int = 7


DEFAULT_CONFIG = PredictorConfig()
