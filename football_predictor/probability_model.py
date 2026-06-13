"""将基本面和市场信号融合为 1X2 概率。"""

from __future__ import annotations

import math
from typing import Dict, List

from .config import DEFAULT_CONFIG, PredictorConfig
from .models import FundamentalAnalysis, MarketDiagnostics, OddsAnalysis, ProbabilityPrediction


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ProbabilityModel:
    def __init__(self, config: PredictorConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    @staticmethod
    def _fundamental_component(analysis: FundamentalAnalysis) -> List[float]:
        diff = analysis.home_score - analysis.away_score
        draw = _clamp(0.30 - abs(diff) * 0.0045, 0.17, 0.30)
        home_share = 1 / (1 + math.exp(-diff / 8.5))
        return [(1 - draw) * home_share, draw, (1 - draw) * (1 - home_share)]

    @staticmethod
    def _asian_component(analysis: OddsAnalysis) -> List[float]:
        draw = 0.27
        home_share = _clamp(0.5 + analysis.asian.home_bias * 0.22, 0.25, 0.75)
        return [(1 - draw) * home_share, draw, (1 - draw) * (1 - home_share)]

    @staticmethod
    def _totals_component(fundamental: FundamentalAnalysis, analysis: OddsAnalysis) -> List[float]:
        expected_goals = analysis.totals.current_expected_goals
        draw = _clamp(0.30 - (expected_goals - 2.25) * 0.075, 0.19, 0.34)
        diff = fundamental.home_score - fundamental.away_score
        home_share = 1 / (1 + math.exp(-diff / 10.0))
        return [(1 - draw) * home_share, draw, (1 - draw) * (1 - home_share)]

    @staticmethod
    def _to_percent(values: List[float]) -> List[float]:
        total = sum(values)
        percentages = [round(value / total * 100, 2) for value in values]
        difference = round(100.0 - sum(percentages), 2)
        percentages[percentages.index(max(percentages))] = round(
            percentages[percentages.index(max(percentages))] + difference, 2
        )
        return percentages

    def _market_diagnostics(
        self,
        fundamental: FundamentalAnalysis,
        odds: OddsAnalysis,
    ) -> MarketDiagnostics:
        fundamental_side = fundamental.tendency if fundamental.tendency in {"主队", "客队"} else "中性"
        european_side = {"主胜": "主队", "客胜": "客队", "平局": "平局"}.get(
            odds.european.tendency, "中性"
        )
        asian_side = odds.asian.tendency if odds.asian.tendency in {"主队", "客队"} else "中性"

        directional_market_sides = [side for side in (european_side, asian_side) if side in {"主队", "客队"}]
        if fundamental_side == "中性":
            fundamental_alignment = "基本面接近，盘口只提供辅助方向，不能单独放大结论"
        elif not directional_market_sides:
            fundamental_alignment = "基本面存在倾向，但盘口未给出清晰验证"
        elif all(side == fundamental_side for side in directional_market_sides):
            fundamental_alignment = "基本面与有效盘口方向一致"
        elif all(side != fundamental_side for side in directional_market_sides):
            fundamental_alignment = "基本面与有效盘口方向相反"
        else:
            fundamental_alignment = "盘口内部信号不统一，对基本面仅形成部分验证"

        if european_side in {"主队", "客队"} and asian_side in {"主队", "客队"}:
            european_asian_alignment = "欧赔与亚盘方向一致" if european_side == asian_side else "欧赔与亚盘方向分歧"
        elif european_side == "平局" and asian_side in {"主队", "客队"}:
            european_asian_alignment = "欧赔偏向平局风险，亚盘偏向一方，存在温和分歧"
        else:
            european_asian_alignment = "欧赔或亚盘方向不明确，暂不判定实质分歧"

        current_probs = odds.european.current_probabilities
        hottest = max(current_probs, key=current_probs.get)
        hottest_probability = current_probs[hottest]
        hottest_rise = odds.european.probability_movements[hottest]
        style = self.config.analysis_style
        is_hot = (
            hottest_probability >= style.hot_probability_threshold
            and hottest_rise >= style.hot_probability_rise_threshold
        )
        hot_direction = (
            f"{hottest}方向偏热（即时隐含概率 {hottest_probability * 100:.2f}%，"
            f"较初盘上升 {hottest_rise * 100:.2f} 个百分点）"
            if is_hot
            else f"未见明显过热（当前最高为{hottest} {hottest_probability * 100:.2f}%）"
        )

        conflict_count = 0
        if fundamental_side in {"主队", "客队"} and asian_side in {"主队", "客队"} and fundamental_side != asian_side:
            conflict_count += 1
        if european_side in {"主队", "客队"} and asian_side in {"主队", "客队"} and european_side != asian_side:
            conflict_count += 1
        elif european_side == "平局" and asian_side in {"主队", "客队"}:
            conflict_count += 1
        if fundamental_side in {"主队", "客队"} and european_side in {"主队", "客队"} and fundamental_side != european_side:
            conflict_count += 1

        shrinkage = style.conservative_base_shrinkage + conflict_count * style.conflict_shrinkage
        if is_hot:
            shrinkage += style.hot_market_shrinkage
        shrinkage = min(shrinkage, style.max_conservative_shrinkage)
        notes = [
            "模型以基本面为主，欧赔、亚盘和大小球仅用于验证、纠偏和风险识别。",
            f"基于当前信号冲突与热度，最终概率向中性基准收缩 {shrinkage * 100:.1f}%。",
        ]
        return MarketDiagnostics(
            fundamental_side=fundamental_side,
            european_side=european_side,
            asian_side=asian_side,
            fundamental_market_alignment=fundamental_alignment,
            european_asian_alignment=european_asian_alignment,
            hot_direction=hot_direction,
            is_hot=is_hot,
            conflict_count=conflict_count,
            conservative_shrinkage=shrinkage,
            notes=notes,
        )

    def predict(self, fundamental: FundamentalAnalysis, odds: OddsAnalysis) -> ProbabilityPrediction:
        fundamental_probs = self._fundamental_component(fundamental)
        european_probs = [
            odds.european.current_probabilities["主胜"],
            odds.european.current_probabilities["平局"],
            odds.european.current_probabilities["客胜"],
        ]
        asian_probs = self._asian_component(odds)
        totals_probs = self._totals_component(fundamental, odds)
        weights = self.config.model_weights

        combined = [
            fundamental_probs[index] * weights.fundamental
            + european_probs[index] * weights.european_odds
            + asian_probs[index] * weights.asian_handicap
            + totals_probs[index] * weights.totals
            for index in range(3)
        ]
        diagnostics = self._market_diagnostics(fundamental, odds)
        neutral_baseline = [0.35, 0.30, 0.35]
        combined = [
            value * (1 - diagnostics.conservative_shrinkage)
            + neutral_baseline[index] * diagnostics.conservative_shrinkage
            for index, value in enumerate(combined)
        ]
        final = self._to_percent(combined)
        names = ("主胜", "平局", "客胜")
        components: Dict[str, Dict[str, float]] = {}
        for component_name, values in {
            "基本面": fundamental_probs,
            "欧赔": european_probs,
            "亚盘": asian_probs,
            "大小球": totals_probs,
        }.items():
            component_percent = self._to_percent(values)
            components[component_name] = dict(zip(names, component_percent))

        return ProbabilityPrediction(
            home_win=final[0],
            draw=final[1],
            away_win=final[2],
            component_probabilities=components,
            component_weights={
                "基本面": weights.fundamental,
                "欧赔": weights.european_odds,
                "亚盘": weights.asian_handicap,
                "大小球": weights.totals,
            },
            diagnostics=diagnostics,
        )
