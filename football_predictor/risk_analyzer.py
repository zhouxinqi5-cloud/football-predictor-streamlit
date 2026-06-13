"""识别信息缺口、信号冲突和特殊赛制风险。"""

from __future__ import annotations

from typing import List

from .models import (
    FundamentalAnalysis,
    MatchInfo,
    MatchType,
    OddsAnalysis,
    ProbabilityPrediction,
    RiskAnalysis,
)


class RiskAnalyzer:
    def analyze(
        self,
        match: MatchInfo,
        fundamental: FundamentalAnalysis,
        odds: OddsAnalysis,
        probability: ProbabilityPrediction,
    ) -> RiskAnalysis:
        score = 0.0
        factors: List[str] = []
        warnings: List[str] = []

        diagnostics = probability.diagnostics
        if diagnostics.is_hot:
            score += 18
            factors.append(f"热门方向风险：{diagnostics.hot_direction}。")

        fundamental_side = fundamental.tendency
        asian_side = odds.asian.tendency
        if fundamental_side in {"主队", "客队"} and asian_side in {"主队", "客队"} and fundamental_side != asian_side:
            score += 22
            factors.append("基本面与亚盘方向冲突。")

        european_side = {"主胜": "主队", "客胜": "客队"}.get(odds.european.tendency)
        if european_side and asian_side in {"主队", "客队"} and european_side != asian_side:
            score += 18
            factors.append("欧赔变化与亚盘方向冲突。")

        if diagnostics.european_side == "平局" and diagnostics.asian_side in {"主队", "客队"}:
            score += 8
            factors.append("欧赔强化平局风险，而亚盘偏向一方，欧亚信号存在温和分歧。")

        if (
            diagnostics.fundamental_side in {"主队", "客队"}
            and diagnostics.european_side in {"主队", "客队"}
            and diagnostics.fundamental_side != diagnostics.european_side
        ):
            score += 14
            factors.append("基本面方向与欧赔变化方向冲突。")

        if not match.home_team.injury_information_complete or not match.away_team.injury_information_complete:
            score += 16
            factors.append("至少一方伤停信息不完整。")

        if match.motivation_certainty < 60:
            score += 13
            factors.append("战意判断存在较高不确定性。")

        abnormal = (
            max(abs(value) for value in odds.european.odds_movements.values()) >= 0.35
            or abs(odds.asian.home_bias) >= 0.75
            or abs(odds.totals.over_bias) >= 0.8
        )
        if abnormal:
            score += 18
            factors.append("临场盘口或赔率变化幅度异常，需要核验消息面。")

        if probability.draw >= 29 or abs(fundamental.home_score - fundamental.away_score) < 3:
            score += 12
            factors.append("双方差距有限，平局风险不可忽视。")

        if match.match_type == MatchType.GROUP and match.is_final_group_round:
            score += 18
            factors.append("小组赛末轮可能受同组形势和策略性结果影响。")
            warnings.append("需同步核对同组另一场比赛、净胜球及实时积分变化。")

        if match.match_type == MatchType.KNOCKOUT:
            score += 10
            factors.append("淘汰赛可能采用更保守策略，常规时间结果波动较大。")

        if odds.asian.insufficient_concession:
            score += 10
            factors.append("强势方存在让步不足信号。")

        score = min(100.0, score)
        level = "低" if score <= 20 else "中" if score <= 45 else "高"
        if not factors:
            factors.append("暂未识别到显著结构性冲突，但样本和消息面仍可能变化。")
        warnings.extend(
            [
                "盘口反映市场定价与情绪，不代表比赛真实概率或确定结果。",
                "伤停、首发、天气和临场信息可能使模型输出快速失效。",
                "本报告仅用于数据分析和比赛研究，不构成投注建议，也不保证准确率。",
            ]
        )
        return RiskAnalysis(level=level, score=round(score, 1), factors=factors, warnings=warnings)
