"""欧赔、亚盘和大小球变化分析。盘口仅作为市场信号。"""

from __future__ import annotations

from typing import Dict, Tuple

from .models import (
    AsianOddsAnalysis,
    EuropeanOdds,
    EuropeanOddsAnalysis,
    FundamentalAnalysis,
    OddsAnalysis,
    OddsData,
    TotalsAnalysis,
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class OddsAnalyzer:
    @staticmethod
    def _implied_probabilities(odds: EuropeanOdds) -> Tuple[Dict[str, float], float]:
        raw = {
            "主胜": 1 / odds.home_win,
            "平局": 1 / odds.draw,
            "客胜": 1 / odds.away_win,
        }
        total = sum(raw.values())
        normalized = {key: value / total for key, value in raw.items()}
        return normalized, 1 / total

    def _analyze_european(self, data: OddsData) -> EuropeanOddsAnalysis:
        opening_probs, opening_return = self._implied_probabilities(data.european_opening)
        current_probs, current_return = self._implied_probabilities(data.european_current)
        opening_values = {
            "主胜": data.european_opening.home_win,
            "平局": data.european_opening.draw,
            "客胜": data.european_opening.away_win,
        }
        current_values = {
            "主胜": data.european_current.home_win,
            "平局": data.european_current.draw,
            "客胜": data.european_current.away_win,
        }
        odds_movements = {key: current_values[key] - opening_values[key] for key in opening_values}
        probability_movements = {key: current_probs[key] - opening_probs[key] for key in opening_probs}
        simplified_kelly = {key: opening_probs[key] * current_values[key] for key in opening_probs}
        strongest = max(probability_movements, key=probability_movements.get)
        tendency = strongest if probability_movements[strongest] > 0.008 else "变化有限"

        explanations = []
        for key in ("主胜", "平局", "客胜"):
            movement = odds_movements[key]
            direction = "下调" if movement < -0.01 else "上调" if movement > 0.01 else "基本不变"
            explanations.append(
                f"{key}赔率{direction} {abs(movement):.2f}，去水后隐含概率变化 {probability_movements[key] * 100:+.2f} 个百分点"
            )
        kelly_low = min(simplified_kelly, key=simplified_kelly.get)
        kelly_spread = max(simplified_kelly.values()) - min(simplified_kelly.values())
        if kelly_spread >= 0.05:
            explanations.append(
                f"简化凯利比较中{kelly_low}值相对较低，显示该方向的即时赔付压缩更明显，但仍需结合其他信号。"
            )
        else:
            explanations.append("三项简化凯利值差异有限，暂未显示明显的单向赔付压缩。")
        explanations.append("简化凯利值仅用于比较初始概率与即时赔率的偏离，不等同于真实凯利公式。")

        return EuropeanOddsAnalysis(
            opening_probabilities=opening_probs,
            current_probabilities=current_probs,
            odds_movements=odds_movements,
            probability_movements=probability_movements,
            opening_return_rate=opening_return,
            current_return_rate=current_return,
            simplified_kelly=simplified_kelly,
            tendency=tendency,
            explanations=explanations,
        )

    @staticmethod
    def _water_direction(change: float) -> str:
        if change < -0.015:
            return "降水"
        if change > 0.015:
            return "升水"
        return "水位稳定"

    def _analyze_asian(self, data: OddsData, fundamental: FundamentalAnalysis) -> AsianOddsAnalysis:
        opening = data.asian_opening
        current = data.asian_current
        strength_diff = fundamental.home_score - fundamental.away_score
        expected = round(_clamp(-strength_diff / 18.0, -2.0, 2.0) * 4) / 4
        opening_reasonable = abs(opening.handicap - expected) <= 0.5

        line_change = current.handicap - opening.handicap
        if line_change < -0.01:
            handicap_movement = "升盘"
        elif line_change > 0.01:
            handicap_movement = "降盘"
        else:
            handicap_movement = "盘口稳定"
        upper_change = current.upper_water - opening.upper_water
        water_movement = self._water_direction(upper_change)
        movement_pattern = f"{handicap_movement}{water_movement}" if handicap_movement != "盘口稳定" else water_movement

        insufficient = False
        if strength_diff >= 7 and opening.handicap > expected + 0.25:
            insufficient = True
        elif strength_diff <= -7 and opening.handicap < expected - 0.25:
            insufficient = True

        line_signal = _clamp(-line_change / 0.5, -1.0, 1.0)
        water_signal = _clamp(-upper_change / 0.15, -1.0, 1.0)
        absolute_line_signal = _clamp(-current.handicap / 1.25, -1.0, 1.0)
        home_bias = _clamp(0.45 * line_signal + 0.25 * water_signal + 0.30 * absolute_line_signal, -1.0, 1.0)
        tendency = "主队" if home_bias > 0.15 else "客队" if home_bias < -0.15 else "中性"

        notes = [f"模型估算合理初盘约为 {expected:+.2f}，实际初盘为 {opening.handicap:+.2f}。"]
        if insufficient:
            notes.append("实力较强一方的让步可能不足，需防范基本面热度与盘口支持不匹配。")
        if movement_pattern in {"升盘升水", "降盘降水"}:
            notes.append(f"出现{movement_pattern}，方向与水位信号并不完全单一。")
        notes.append("亚盘判断反映市场定价变化，不构成确定性赛果结论。")

        return AsianOddsAnalysis(
            opening_reasonable=opening_reasonable,
            expected_handicap=expected,
            handicap_movement=handicap_movement,
            water_movement=water_movement,
            movement_pattern=movement_pattern,
            insufficient_concession=insufficient,
            home_bias=home_bias,
            tendency=tendency,
            risk_notes=notes,
        )

    def _analyze_totals(self, data: OddsData) -> TotalsAnalysis:
        opening, current = data.totals_opening, data.totals_current
        line_change = current.line - opening.line
        if line_change > 0.01:
            movement = "升盘"
        elif line_change < -0.01:
            movement = "降盘"
        else:
            movement = "盘口稳定"
        over_change = current.over_water - opening.over_water
        under_change = current.under_water - opening.under_water
        line_signal = _clamp(line_change / 0.5, -1.0, 1.0)
        water_signal = _clamp(-over_change / 0.15, -1.0, 1.0)
        over_bias = _clamp(line_signal * 0.65 + water_signal * 0.35, -1.0, 1.0)
        tendency = "偏大" if over_bias > 0.15 else "偏小" if over_bias < -0.15 else "中性"
        expected_goals = max(0.2, current.line + over_bias * 0.20)

        explanations = [
            f"大小球由 {opening.line:.2f} 变为 {current.line:.2f}（{movement}）。",
            f"大球水位变化 {over_change:+.2f}，小球水位变化 {under_change:+.2f}。",
            "进球数倾向会与双方攻防数据共同使用，不单独决定比分。",
        ]
        return TotalsAnalysis(
            opening_expected_goals=opening.line,
            current_expected_goals=expected_goals,
            line_movement=movement,
            over_water_movement=over_change,
            under_water_movement=under_change,
            over_bias=over_bias,
            tendency=tendency,
            explanations=explanations,
        )

    def analyze(self, data: OddsData, fundamental: FundamentalAnalysis) -> OddsAnalysis:
        return OddsAnalysis(
            european=self._analyze_european(data),
            asian=self._analyze_asian(data, fundamental),
            totals=self._analyze_totals(data),
        )
