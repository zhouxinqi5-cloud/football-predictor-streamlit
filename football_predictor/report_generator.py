"""生成结构化中文文本报告。"""

from __future__ import annotations

from .models import (
    FundamentalAnalysis,
    MatchInfo,
    OddsAnalysis,
    OddsData,
    ProbabilityPrediction,
    RiskAnalysis,
    ScorePrediction,
)


class ReportGenerator:
    @staticmethod
    def _percent_map(values: dict[str, float]) -> str:
        return "，".join(f"{key} {value * 100:.2f}%" for key, value in values.items())

    def generate(
        self,
        match: MatchInfo,
        odds_data: OddsData,
        fundamental: FundamentalAnalysis,
        odds: OddsAnalysis,
        probability: ProbabilityPrediction,
        scores: ScorePrediction,
        risk: RiskAnalysis,
    ) -> str:
        home, away = match.home_team, match.away_team
        european = odds.european
        asian = odds.asian
        totals = odds.totals
        diagnostics = probability.diagnostics
        weight_text = "，".join(
            f"{name} {weight * 100:.0f}%" for name, weight in probability.component_weights.items()
        )
        candidates = "、".join(
            f"{item.score}（区间 {item.probability_range}）" for item in scores.candidates
        )
        goal_ranges = "，".join(f"{key} {value:.2f}%" for key, value in scores.goal_ranges.items())
        leading_result = max(
            (("主胜", probability.home_win), ("平局", probability.draw), ("客胜", probability.away_win)),
            key=lambda item: item[1],
        )
        conclusion = (
            f"融合模型目前将“{leading_result[0]}”列为相对较高概率结果（{leading_result[1]:.2f}%），"
            f"基本面倾向为{fundamental.tendency}。一致性判断：{diagnostics.fundamental_market_alignment}；"
            f"欧亚关系：{diagnostics.european_asian_alignment}；热门评估：{diagnostics.hot_direction}。"
            f"市场辅助信号为欧赔{european.tendency}、亚盘{asian.tendency}、进球数{totals.tendency}。"
            f"模型已进行 {diagnostics.conservative_shrinkage * 100:.1f}% 的保守收缩。该结论是当前输入条件下的概率排序，"
            "并非确定赛果；临场首发和盘口变化应重新计算。"
        )

        lines = [
            "=" * 72,
            "足球比赛预测分析报告",
            "=" * 72,
            f"分析风格：基本面为主，盘口和指数为辅（{weight_text}）",
            "判断原则：先看基本面，再检查盘口一致性、热门过热与欧亚分歧，最终采用保守概率。",
            "",
            "【1. 比赛信息】",
            f"对阵：{home.name} vs {away.name}",
            f"时间：{match.kickoff_time:%Y-%m-%d %H:%M}",
            f"类型：{match.match_type.value}｜场地：{match.venue}｜中立场：{'是' if match.neutral_venue else '否'}",
            f"天气：{match.weather}｜旅行距离：{match.travel_distance_km:.0f} km",
            f"积分形势：{match.standings_context}",
            f"出线形势：{match.qualification_context}",
            f"战意：{match.motivation_description}",
            "",
            "【2. 基本面分析】",
            f"{home.name}评分：{fundamental.home_score:.2f}｜{away.name}评分：{fundamental.away_score:.2f}",
            f"基本面倾向：{fundamental.tendency}",
            *[f"- {reason}" for reason in fundamental.reasons],
            f"战术风格：{home.name}——{home.tactical_style}；{away.name}——{away.tactical_style}",
            f"关键球员：{home.name}——{home.key_player_status}；{away.name}——{away.key_player_status}",
            "",
            "【3. 欧赔分析】",
            f"公司：{odds_data.bookmaker}｜更新时间：{odds_data.updated_at:%Y-%m-%d %H:%M}",
            f"初盘去水概率：{self._percent_map(european.opening_probabilities)}",
            f"即时去水概率：{self._percent_map(european.current_probabilities)}",
            f"初盘返还率：{european.opening_return_rate * 100:.2f}%｜即时返还率：{european.current_return_rate * 100:.2f}%",
            f"简化凯利比较：{', '.join(f'{key} {value:.3f}' for key, value in european.simplified_kelly.items())}",
            *[f"- {item}" for item in european.explanations],
            "",
            "【4. 亚盘分析】",
            f"初盘：{odds_data.asian_opening.handicap:+.2f}，上/下盘水位 {odds_data.asian_opening.upper_water:.2f}/{odds_data.asian_opening.lower_water:.2f}",
            f"即时：{odds_data.asian_current.handicap:+.2f}，上/下盘水位 {odds_data.asian_current.upper_water:.2f}/{odds_data.asian_current.lower_water:.2f}",
            f"变化：{asian.movement_pattern}｜初盘合理性：{'大致合理' if asian.opening_reasonable else '与模型估值有偏差'}",
            f"市场倾向：{asian.tendency}｜强队让步不足：{'是' if asian.insufficient_concession else '否'}",
            *[f"- {item}" for item in asian.risk_notes],
            "",
            "【5. 大小球分析】",
            f"初盘：{odds_data.totals_opening.line:.2f}，大/小球水位 {odds_data.totals_opening.over_water:.2f}/{odds_data.totals_opening.under_water:.2f}",
            f"即时：{odds_data.totals_current.line:.2f}，大/小球水位 {odds_data.totals_current.over_water:.2f}/{odds_data.totals_current.under_water:.2f}",
            f"变化：{totals.line_movement}｜进球数倾向：{totals.tendency}｜调整后进球预期：{totals.current_expected_goals:.2f}",
            *[f"- {item}" for item in totals.explanations],
            "",
            "【6. 概率预测】",
            f"主胜 {probability.home_win:.2f}%｜平局 {probability.draw:.2f}%｜客胜 {probability.away_win:.2f}%",
            f"模型权重：{weight_text}",
            f"基本面与盘口：{diagnostics.fundamental_market_alignment}",
            f"热门方向：{diagnostics.hot_direction}",
            f"欧赔与亚盘：{diagnostics.european_asian_alignment}",
            f"保守调整：向中性概率收缩 {diagnostics.conservative_shrinkage * 100:.1f}%",
            *[f"- {item}" for item in diagnostics.notes],
            "注：三项概率已归一化，总和为 100%。",
            "",
            "【7. 可能比分】",
            f"预期进球：{home.name} {scores.home_expected_goals:.2f}，{away.name} {scores.away_expected_goals:.2f}",
            f"较高概率比分：{candidates}",
            f"总进球区间：{goal_ranges}",
            "",
            "【8. 风险提示】",
            f"风险等级：{risk.level}（风险分 {risk.score:.1f}/100）",
            *[f"- {item}" for item in risk.factors],
            *[f"- {item}" for item in risk.warnings],
            "",
            "【9. 综合结论】",
            conclusion,
            "=" * 72,
        ]
        return "\n".join(lines)
