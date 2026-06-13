"""Pipeline orchestration and professional Chinese report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from football_ai.config import MatchContext, MatchFixture, OddsInput
from football_ai.core.feature_engine import FeatureAnalysis, FeatureEngine
from football_ai.core.market_behavior import MarketBehaviorAnalysis, MarketBehaviorEngine
from football_ai.core.odds_engine import OddsAnalysis, OddsEngine
from football_ai.core.probability_engine import ProbabilityAnalysis, ProbabilityEngine
from football_ai.core.risk_engine import RiskAnalysis, RiskEngine


@dataclass(frozen=True)
class ProAnalysisResult:
    fixture: MatchFixture
    features: FeatureAnalysis
    odds: OddsAnalysis
    market: MarketBehaviorAnalysis
    probability: ProbabilityAnalysis
    risk: RiskAnalysis
    report: str


class ReportEngine:
    @staticmethod
    def _side(value: str) -> str:
        return {"home": "主队", "draw": "平局", "away": "客队", "even": "均衡"}.get(value, value)

    def generate(
        self,
        fixture: MatchFixture,
        features: FeatureAnalysis,
        odds: OddsAnalysis,
        market: MarketBehaviorAnalysis,
        probability: ProbabilityAnalysis,
        risk: RiskAnalysis,
    ) -> str:
        score_text = "、".join(f"{item.score}（{item.probability:.1f}%）" for item in probability.score_distribution)
        factors = "\n".join(f"- {item}" for item in risk.factors)
        neutral = "是" if fixture.neutral_ground else "否"
        trend = self._side(features.match_tendency)
        market_bias = self._side(market.market_bias)
        defensive = self._side(market.defensive_side)
        return f"""# Pro Football Analytics Engine 足球比赛预测分析报告

## 1. 比赛信息
- 对阵：{fixture.home_team} vs {fixture.away_team}
- 赛事：{fixture.league}（{fixture.competition_code}）
- 开球时间：{fixture.kickoff_time:%Y-%m-%d %H:%M %Z}
- 中立场：{neutral}
- 比赛数据来源：{fixture.source}

## 2. 基本面对比
- 主队综合力量：{features.home_power_score:.1f}/100
- 客队综合力量：{features.away_power_score:.1f}/100
- 强度差：{features.strength_gap:+.1f}，基本面倾向：{trend}
- Elo-like：{features.home.elo_like_rating:.0f} vs {features.away.elo_like_rating:.0f}
- 近期状态：{features.home.recent_form_score:.1f} vs {features.away.recent_form_score:.1f}
- 攻击/防守：{features.home.attack_strength:.1f}/{features.home.defense_strength:.1f} vs {features.away.attack_strength:.1f}/{features.away.defense_strength:.1f}
- 疲劳指数：{features.home.fatigue_index:.1f} vs {features.away.fatigue_index:.1f}
- 数据说明：{features.source}

## 3. 盘口解读
- 欧赔即时隐含概率：主 {odds.current_probabilities['home'] * 100:.1f}% / 平 {odds.current_probabilities['draw'] * 100:.1f}% / 客 {odds.current_probabilities['away'] * 100:.1f}%
- 即时返还率：{odds.current_return_rate:.2f}%
- 亚盘结构：{odds.asian_pattern}，方向：{self._side(odds.asian_bias)}
- 欧亚一致性：{odds.market_consistency}
- 大小球：预期总进球 {odds.expected_goals_opening:.2f} → {odds.expected_goals_current:.2f}，倾向 {odds.totals_tendency}

## 4. 市场行为判断
- 市场偏向：{market_bias}
- 热门拥挤度代理：{market.public_money:.0f}/100
- 防守方向代理：{defensive}
- Sharp money 信号：{market.sharp_money_signal}
- 诱盘指标：{market.trap_indicator:.0f}/100
- 控盘倾向：{market.control_tendency}
- 说明：此部分仅由公开赔率结构计算，不能证明真实资金流或庄家主观意图。

## 5. 概率预测
- 主胜：{probability.home_win:.2f}%
- 平局：{probability.draw:.2f}%
- 客胜：{probability.away_win:.2f}%
- 模型置信度：{probability.confidence:.1f}/100
- 融合原则：基本面为主（50%），盘口与市场行为为辅，并对冲突及热门过热进行保守收缩。

## 6. 比分模型
- xG 代理：主 {probability.home_expected_goals:.2f} / 客 {probability.away_expected_goals:.2f}
- 可能比分：{score_text}
- 进球区间：0-1球 {probability.goal_ranges['0-1球']:.1f}% / 2-3球 {probability.goal_ranges['2-3球']:.1f}% / 4球以上 {probability.goal_ranges['4球以上']:.1f}%

## 7. 风险等级
- 风险等级：{risk.risk_level}
- 风险分数：{risk.risk_score:.1f}/100
{factors}

## 8. 分析优先级
- 推荐等级：{risk.recommendation_grade}
- 等级含义：A/B/C 仅表示模型认为该场比赛的分析清晰度与数据一致性，不是投注建议，也不代表结果保证。

## 风险提示
本系统仅用于足球数据分析、概率建模、比赛研究与学习，不构成投注建议。模型输入可能不完整，阵容、伤停、战意和临场盘口会快速变化；任何概率均不等于确定结果。系统不提供“稳赚”“必胜”或具体投注指令，不保证预测准确率，请独立判断并理性使用。
"""


class ProFootballAnalyticsEngine:
    """Run the full API/mock-to-report analysis pipeline."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.features = FeatureEngine(api_key=api_key)
        self.odds = OddsEngine()
        self.market = MarketBehaviorEngine()
        self.probability = ProbabilityEngine()
        self.risk = RiskEngine()
        self.report = ReportEngine()

    def analyze(
        self,
        fixture: MatchFixture,
        odds_input: Optional[OddsInput] = None,
        context: Optional[MatchContext] = None,
    ) -> ProAnalysisResult:
        context = context or MatchContext()
        if odds_input is None:
            from football_ai.data.mock_data import MockDataProvider

            odds_input = MockDataProvider().odds(fixture)
        feature_result = self.features.analyze(fixture, context)
        odds_result = self.odds.analyze(odds_input, feature_result)
        market_result = self.market.analyze(feature_result, odds_result)
        probability_result = self.probability.analyze(feature_result, odds_result, market_result)
        risk_result = self.risk.analyze(feature_result, odds_result, market_result, probability_result, context)
        report = self.report.generate(
            fixture,
            feature_result,
            odds_result,
            market_result,
            probability_result,
            risk_result,
        )
        return ProAnalysisResult(
            fixture=fixture,
            features=feature_result,
            odds=odds_result,
            market=market_result,
            probability=probability_result,
            risk=risk_result,
            report=report,
        )
