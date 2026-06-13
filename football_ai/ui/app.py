"""Streamlit interface for the professional football analytics engine."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, datetime, time
from typing import Iterable, Optional

import streamlit as st
from dotenv import load_dotenv

from football_ai.config import (
    AsianOdds,
    EuropeanOdds,
    MatchContext,
    MatchFixture,
    OddsInput,
    TeamMotivation,
    TotalsOdds,
)
from football_ai.core.match_loader import MatchLoadResult, MatchLoader
from football_ai.core.report_engine import ProAnalysisResult, ProFootballAnalyticsEngine
from football_ai.data.mock_data import LEAGUES, MockDataProvider
from football_ai.team_name_mapper import display_league_name, display_team_name


load_dotenv()


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def _match_loader(api_key: str) -> MatchLoader:
    disabled = os.getenv("FOOTBALL_AI_DISABLE_EXTERNAL_APIS", "").strip().lower() in {"1", "true", "yes"}
    return MatchLoader(api_key=api_key or None, enable_fallback_apis=not disabled)


def _ensure_fixture_fallback(load_result: MatchLoadResult, competition_codes: Iterable[str]) -> MatchLoadResult:
    """Repair empty provider responses and stale Streamlit sessions with explicit mock data."""
    if load_result.fixtures:
        return load_result
    codes = tuple(competition_codes) or ("ALL",)
    mock_fixtures = MockDataProvider().fixtures(load_result.target_date, codes)
    reason = load_result.fallback_reason or "所有真实数据源均未返回比赛"
    failures = load_result.failures + ("真实比赛列表为空，已切换模拟示例数据",)
    return replace(
        load_result,
        fixtures=mock_fixtures,
        source="mock",
        fallback_reason=reason,
        failures=failures,
    )


def _initialize(api_key: str) -> None:
    defaults = {
        "pro_fixtures": [],
        "pro_fixture": None,
        "pro_load_result": None,
        "pro_result": None,
        "pro_show_report": False,
        "pro_top_results": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.pro_load_result is None or not st.session_state.pro_fixtures:
        load_result = _ensure_fixture_fallback(
            _match_loader(api_key).load_with_status(date.today(), ["ALL"]),
            ["ALL"],
        )
        st.session_state.pro_load_result = load_result
        st.session_state.pro_fixtures = load_result.fixtures
        st.session_state.pro_fixture = load_result.fixtures[0] if load_result.fixtures else None


def _odds_inputs(defaults: OddsInput, prefix: str) -> OddsInput:
    st.markdown("**欧赔（初盘 / 即时盘）**")
    columns = st.columns(6)
    labels = ("初主", "初平", "初客", "即主", "即平", "即客")
    values = (
        defaults.european_opening.home,
        defaults.european_opening.draw,
        defaults.european_opening.away,
        defaults.european_current.home,
        defaults.european_current.draw,
        defaults.european_current.away,
    )
    european = [
        column.number_input(label, min_value=1.01, max_value=30.0, value=float(value), step=0.01, key=f"{prefix}_eu_{index}")
        for index, (column, label, value) in enumerate(zip(columns, labels, values))
    ]
    st.markdown("**亚盘（负数表示主让）**")
    columns = st.columns(6)
    asian_labels = ("初盘口", "初主水", "初客水", "即盘口", "即主水", "即客水")
    asian_values = (
        defaults.asian_opening.handicap,
        defaults.asian_opening.home_water,
        defaults.asian_opening.away_water,
        defaults.asian_current.handicap,
        defaults.asian_current.home_water,
        defaults.asian_current.away_water,
    )
    asian = [
        column.number_input(label, min_value=-3.0 if index in (0, 3) else 0.5, max_value=3.0 if index in (0, 3) else 1.5, value=float(value), step=0.01, key=f"{prefix}_ah_{index}")
        for index, (column, label, value) in enumerate(zip(columns, asian_labels, asian_values))
    ]
    st.markdown("**大小球**")
    columns = st.columns(6)
    total_labels = ("初盘口", "初大水", "初小水", "即盘口", "即大水", "即小水")
    total_values = (
        defaults.totals_opening.line,
        defaults.totals_opening.over_water,
        defaults.totals_opening.under_water,
        defaults.totals_current.line,
        defaults.totals_current.over_water,
        defaults.totals_current.under_water,
    )
    totals = [
        column.number_input(label, min_value=0.0 if index in (0, 3) else 0.5, max_value=6.0 if index in (0, 3) else 1.5, value=float(value), step=0.01, key=f"{prefix}_ou_{index}")
        for index, (column, label, value) in enumerate(zip(columns, total_labels, total_values))
    ]
    return OddsInput(
        european_opening=EuropeanOdds(*european[:3]),
        european_current=EuropeanOdds(*european[3:]),
        asian_opening=AsianOdds(*asian[:3]),
        asian_current=AsianOdds(*asian[3:]),
        totals_opening=TotalsOdds(*totals[:3]),
        totals_current=TotalsOdds(*totals[3:]),
        source="manual / editable baseline",
    )


def _context_inputs(prefix: str) -> MatchContext:
    with st.expander("赛程、旅行与战意修正", expanded=False):
        columns = st.columns(2)
        home_travel = columns[0].number_input("主队旅行距离（公里）", 0.0, 20000.0, 0.0, 50.0, key=f"{prefix}_home_travel")
        away_travel = columns[1].number_input("客队旅行距离（公里）", 0.0, 20000.0, 300.0, 50.0, key=f"{prefix}_away_travel")
        known = st.checkbox("战意信息已人工确认", key=f"{prefix}_motivation_known")
        final_group = st.checkbox("小组赛最后一轮", key=f"{prefix}_final_group")
        knockout = st.checkbox("淘汰赛", key=f"{prefix}_knockout")
        if known:
            st.caption("以下指数为 0-100，仅用于表达压力强度。")
            values = []
            for side in ("主队", "客队"):
                columns = st.columns(3)
                values.append(tuple(
                    column.slider(f"{side}{label}", 0, 100, 50, key=f"{prefix}_{side}_{index}")
                    for index, (column, label) in enumerate(zip(columns, ("争冠压力", "保级压力", "出线压力")))
                ))
            home_motivation = TeamMotivation(*values[0], certainty=80)
            away_motivation = TeamMotivation(*values[1], certainty=80)
        else:
            home_motivation = TeamMotivation()
            away_motivation = TeamMotivation()
    return MatchContext(
        home_motivation=home_motivation,
        away_motivation=away_motivation,
        home_travel_km=home_travel,
        away_travel_km=away_travel,
        motivation_known=known,
        final_group_round=final_group,
        knockout_match=knockout,
    )


def _analyze(fixture: MatchFixture, odds: OddsInput, context: MatchContext) -> ProAnalysisResult:
    return ProFootballAnalyticsEngine(api_key=_secret("FOOTBALL_DATA_API_KEY") or None).analyze(fixture, odds, context)


def _render_result(result: ProAnalysisResult, show_report: bool) -> None:
    home_name = display_team_name(result.fixture.home_team)
    away_name = display_team_name(result.fixture.away_team)
    st.subheader(f"{home_name} vs {away_name}")
    columns = st.columns(4)
    columns[0].metric("主队基本面", f"{result.features.home_power_score:.1f}", f"{result.features.strength_gap:+.1f}")
    columns[1].metric("客队基本面", f"{result.features.away_power_score:.1f}")
    columns[2].metric("风险等级", result.risk.risk_level, f"{result.risk.risk_score:.1f}/100")
    columns[3].metric("推荐等级", result.risk.recommendation_grade, "分析清晰度")

    st.markdown("**胜平负概率**")
    for label, value in (
        ("主胜", result.probability.home_win),
        ("平局", result.probability.draw),
        ("客胜", result.probability.away_win),
    ):
        left, right = st.columns([1, 5])
        left.write(f"{label} {value:.2f}%")
        right.progress(int(round(value)))
    columns = st.columns(3)
    columns[0].metric("市场方向", result.market.market_bias.upper())
    columns[1].metric("热门拥挤度", f"{result.market.public_money:.0f}/100")
    columns[2].metric("诱盘指标", f"{result.market.trap_indicator:.0f}/100")
    st.caption("市场方向与诱盘指标均为公开赔率结构的计算代理，不代表真实资金流或庄家内部意图。")
    if show_report:
        st.code(result.report, language="markdown")
        st.download_button(
            "下载分析报告",
            result.report,
            file_name=f"{home_name}_vs_{away_name}.md",
            mime="text/markdown",
        )


def _auto_mode(
    competition_codes: Iterable[str],
) -> tuple[Optional[MatchFixture], Optional[OddsInput], Optional[MatchContext] | dict]:
    columns = st.columns([2, 3, 2, 2])
    target_date = columns[0].date_input("比赛日期", date.today(), key="auto_date")
    selected_codes = columns[1].multiselect(
        "联赛筛选",
        options=list(LEAGUES),
        default=list(competition_codes),
        format_func=lambda code: f"{LEAGUES[code]}（{code}）",
        key="auto_codes",
    )
    fetch_clicked = columns[2].button("自动获取比赛", type="primary", width="stretch")
    refresh_today = columns[3].button("刷新今日比赛", width="stretch")
    query_date = date.today() if refresh_today else target_date
    st.markdown(f"**当前查询日期：{query_date:%Y-%m-%d}**")
    if fetch_clicked or refresh_today:
        with st.spinner("正在读取赛程；API 不可用时自动切换 mock 数据..."):
            fallback_codes = selected_codes or ["ALL"]
            load_result = _ensure_fixture_fallback(
                _match_loader(_secret("FOOTBALL_DATA_API_KEY")).load_with_status(query_date, fallback_codes),
                fallback_codes,
            )
        st.session_state.pro_load_result = load_result
        st.session_state.pro_fixtures = load_result.fixtures
        st.session_state.pro_fixture = load_result.fixtures[0] if load_result.fixtures else None
        st.session_state.pro_result = None
        st.session_state.pro_show_report = False
        st.session_state.pro_top_results = []

    fixtures = list(st.session_state.get("pro_fixtures") or [])
    st.session_state.pro_fixtures = fixtures
    load_result: MatchLoadResult = st.session_state.pro_load_result
    if len(fixtures) == 0:
        st.warning(
            "当前没有获取到比赛数据。请检查 Football-Data API Key、日期、赛事选择，或切换到手动模式。"
        )
        st.info("如果没有配置 API Key，当前不会显示真实比赛。可以使用手动输入模式继续分析。")
        st.session_state.pro_fixture = None
        st.session_state.pro_top_results = []
        return None, None, {}

    if load_result.is_real_data:
        source_labels = {
            "football-data": "Football-Data.org",
            "thesportsdb": "TheSportsDB",
            "openligadb": "OpenLigaDB",
        }
        st.success(
            f"当前使用 {source_labels.get(load_result.source, load_result.source)} 真实 API 数据。"
            f"查询日期：{load_result.target_date:%Y-%m-%d}，"
            f"共获取 {len(load_result.fixtures)} 场比赛。"
        )
        if load_result.source == "thesportsdb":
            st.caption("TheSportsDB 免费接口可能限制单次返回数量，列表不一定覆盖当天全部赛事。")
        if load_result.failures:
            with st.expander("查看上游数据源回退记录"):
                for failure in load_result.failures:
                    st.write(f"- {failure}")
    else:
        st.warning("当前没有获取到真实比赛数据，请检查 API Key、日期或赛事选择。")
        if load_result.api_configured and load_result.fallback_reason:
            st.error(f"真实 API 获取失败：{load_result.fallback_reason}")
        elif not load_result.api_configured:
            st.warning("当前未配置 Football-Data API Key，使用模拟数据或手动输入模式。")
        st.warning("当前使用的是模拟示例数据，不是真实近期比赛。")
        st.caption(f"模拟数据对应查询日期：{load_result.target_date:%Y-%m-%d}，仅用于演示模型流程。")
    st.dataframe(
        [
            {
                "比赛时间": item.kickoff_time.strftime("%Y-%m-%d %H:%M"),
                "赛事": display_league_name(item.league, item.competition_code),
                "主队": display_team_name(item.home_team),
                "客队": display_team_name(item.away_team),
                "数据来源": {
                    "football-data": "Football-Data.org",
                    "thesportsdb": "TheSportsDB",
                    "openligadb": "OpenLigaDB",
                    "mock": "模拟示例",
                }.get(item.source, item.source),
            }
            for item in fixtures
        ],
        width="stretch",
        hide_index=True,
    )
    fixture = st.selectbox("选择比赛", fixtures, format_func=lambda item: item.label, key="auto_fixture")
    st.session_state.pro_fixture = fixture

    mock_odds = MockDataProvider().odds(fixture)
    if not load_result.is_real_data:
        st.info("没有真实 API 基本面时，系统将使用 mock_data 自动生成基础评分；也可切换手动模式自行输入球队和比赛背景。")
    st.info("赔率、亚盘、大小球需要手动输入；当前未接入付费赔率 API。下方预填值仅为可编辑的模型示例基线。")
    with st.expander("手动输入赔率、亚盘和大小球", expanded=False):
        odds = _odds_inputs(mock_odds, "auto")
    context = _context_inputs("auto")
    if st.button("自动生成基本面评分", width="stretch"):
        with st.spinner("正在构建 Elo-like、近期状态、攻防、疲劳与动机特征..."):
            st.session_state.pro_result = _analyze(fixture, odds, context)
        st.session_state.pro_show_report = False
        st.success("自动基本面已生成，并完成盘口、市场行为、概率与风险模型计算。")

    # The empty-list guard above returns before this block, so both bounds are always >= 1.
    top_n_max = min(5, len(fixtures))
    default_top_n = min(3, top_n_max)
    top_n = st.slider(
        "Top N 分析数量",
        min_value=1,
        max_value=top_n_max,
        value=default_top_n,
    )
    if st.button("一键分析 Top N 比赛", width="stretch"):
        results = []
        with st.spinner("正在批量计算..."):
            for candidate in fixtures[:top_n]:
                results.append(_analyze(candidate, MockDataProvider().odds(candidate), MatchContext()))
        st.session_state.pro_top_results = sorted(
            results,
            key=lambda item: (item.risk.recommendation_grade, item.risk.risk_score, -abs(item.features.strength_gap)),
        )
    if st.session_state.pro_top_results:
        st.dataframe(
            [
                {
                    "比赛": f"{display_team_name(item.fixture.home_team)} vs {display_team_name(item.fixture.away_team)}",
                    "基本面差": item.features.strength_gap,
                    "主/平/客": f"{item.probability.home_win:.1f}/{item.probability.draw:.1f}/{item.probability.away_win:.1f}",
                    "风险": f"{item.risk.risk_level} {item.risk.risk_score:.0f}",
                    "等级": item.risk.recommendation_grade,
                }
                for item in st.session_state.pro_top_results
            ],
            width="stretch",
            hide_index=True,
        )
    return fixture, odds, context


def _manual_mode() -> tuple[MatchFixture, OddsInput, MatchContext]:
    columns = st.columns(2)
    home_team = columns[0].text_input("主队", "巴西")
    away_team = columns[1].text_input("客队", "摩洛哥")
    columns = st.columns(4)
    match_date = columns[0].date_input("日期", date.today(), key="manual_date")
    match_time = columns[1].time_input("时间", time(20, 0))
    competition = columns[2].selectbox("比赛类型", ["联赛", "小组赛", "淘汰赛", "友谊赛"])
    neutral = columns[3].checkbox("中立场")
    league = st.text_input("赛事名称", "手动比赛")
    fixture = MatchFixture(
        match_id=f"manual-{home_team}-{away_team}-{match_date}",
        home_team=home_team,
        away_team=away_team,
        league=league,
        competition_code="MANUAL",
        kickoff_time=datetime.combine(match_date, match_time),
        neutral_ground=neutral,
        source="manual",
        home_team_id=1,
        away_team_id=2,
    )
    st.text_area("伤停情况（记录用途，当前量化模型不自动解析自然语言）", "暂无完整伤停信息")
    st.text_area("战意描述（记录用途；下方指数用于模型计算）", "战意待确认")
    odds = _odds_inputs(MockDataProvider().odds(fixture), "manual")
    context = _context_inputs("manual")
    if competition == "小组赛":
        context = MatchContext(**{**context.__dict__, "final_group_round": context.final_group_round})
    elif competition == "淘汰赛":
        context = MatchContext(**{**context.__dict__, "knockout_match": True})
    st.session_state.pro_fixture = fixture
    return fixture, odds, context


def main() -> None:
    st.set_page_config(page_title="Pro Football Analytics Engine", page_icon="⚽", layout="wide")
    api_key = _secret("FOOTBALL_DATA_API_KEY")
    _initialize(api_key)
    st.title("Pro Football Analytics Engine")
    st.caption("职业级足球量化分析系统 · API + 计算 · 无网页爬虫 · 无付费服务强依赖")
    st.warning("仅用于数据分析、概率研究和学习，不构成投注建议，不保证预测准确率。")
    api_status = "已配置，优先读取真实赛程" if api_key else "未配置，将尝试 TheSportsDB / OpenLigaDB 免费备用源"
    st.sidebar.markdown(f"**Football-Data API：** {api_status}")
    if not api_key:
        st.sidebar.warning("当前未配置 Football-Data API Key，使用模拟数据或手动输入模式。免费备用源可用时会优先显示真实比赛。")
        st.sidebar.warning("建议配置免费 Key，以获得更完整的赛程、积分榜和近期战绩：")
        st.sidebar.code('FOOTBALL_DATA_API_KEY = "你的 API Key"', language="toml")
        st.sidebar.caption("配置后重新启动应用，再点击“刷新今日比赛”。")
    st.sidebar.markdown("**备用真实数据：** TheSportsDB → OpenLigaDB")
    st.sidebar.caption("备用源无需私有 Key，但覆盖范围和免费返回数量有限。ODDS_API_KEY 仅为后续接口预留。")

    mode = st.radio("分析模式", ["自动模式", "手动模式"], horizontal=True)
    if mode == "自动模式":
        fixture, odds, context = _auto_mode(["ALL"])
    else:
        fixture, odds, context = _manual_mode()

    can_analyze = fixture is not None and odds is not None and isinstance(context, MatchContext)
    if st.button("生成分析报告", type="primary", width="stretch", disabled=not can_analyze):
        with st.spinner("正在运行完整量化分析链路..."):
            st.session_state.pro_result = _analyze(fixture, odds, context)
        st.session_state.pro_show_report = True

    result: Optional[ProAnalysisResult] = st.session_state.pro_result
    if result is not None:
        _render_result(result, st.session_state.pro_show_report)


if __name__ == "__main__":
    main()
