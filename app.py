"""个人足球预测分析工具的 Streamlit 入口。"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

from football_predictor.analysis_service import generate_report
from football_predictor.data_fetcher import FootballDataError, FootballDataFetcher
from football_predictor.feature_engine import FeatureEngine, MatchFeatureResult
from football_predictor.fixture_fetcher import COMPETITIONS, Fixture, FixtureFetcher
from football_predictor.match_recommender import MatchRecommender
from football_predictor.models import (
    AsianHandicapOdds,
    EuropeanOdds,
    HeadToHead,
    InjuryInfo,
    MatchInfo,
    MatchType,
    OddsData,
    TeamInfo,
    TotalsOdds,
    VenuePerformance,
)
from football_predictor.odds_fetcher import OddsFetcher


load_dotenv()


def get_secret(name: str) -> str:
    """优先读取环境变量，其次读取 Streamlit secrets。"""
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        secret_value = st.secrets.get(name, "")
    except Exception:
        secret_value = ""
    return str(secret_value).strip() if secret_value else ""


def initialize_state() -> None:
    defaults: Dict[str, Any] = {
        "home_name": "Arsenal FC",
        "away_name": "Chelsea FC",
        "competition_code": "PL",
        "fixture_date": date.today(),
        "fixture_codes": ["PL", "PD", "BL1", "SA", "FL1"],
        "available_fixtures": [],
        "selected_fixture_id": None,
        "feature_result": None,
        "match_date": date.today(),
        "match_time": time(20, 0),
        "match_type": MatchType.LEAGUE.value,
        "neutral_venue": False,
        "home_recent": "胜 平 胜 负 胜",
        "away_recent": "平 胜 负 胜 平",
        "home_strength": 78.0,
        "away_strength": 76.0,
        "home_attack": 78.0,
        "away_attack": 75.0,
        "home_defense": 76.0,
        "away_defense": 74.0,
        "home_key_status": "暂无明确关键球员信息",
        "away_key_status": "暂无明确关键球员信息",
        "home_key_availability": 80,
        "away_key_availability": 80,
        "home_injuries": "",
        "away_injuries": "",
        "home_injury_complete": False,
        "away_injury_complete": False,
        "home_tactics": "战术信息待补充",
        "away_tactics": "战术信息待补充",
        "home_fitness": 75,
        "away_fitness": 75,
        "home_schedule_density": 50,
        "away_schedule_density": 50,
        "home_weather_adapt": 70,
        "away_weather_adapt": 70,
        "home_home_rating": 75,
        "away_home_rating": 75,
        "home_away_rating": 70,
        "away_away_rating": 70,
        "home_neutral_rating": 70,
        "away_neutral_rating": 70,
        "home_pitch_adapt": 70,
        "away_pitch_adapt": 70,
        "weather": "天气信息待确认",
        "venue": "比赛场地待确认",
        "travel_distance": 0.0,
        "standings_context": "请手动填写积分排名，或使用自动获取功能。",
        "qualification_context": "请根据赛制手动填写。",
        "motivation_description": "请结合积分、轮换和赛程手动判断。",
        "home_motivation": 75,
        "away_motivation": 75,
        "motivation_certainty": 55,
        "final_group_round": False,
        "auto_summary": "",
        "report": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def parse_recent_results(raw: str) -> List[str]:
    mapping = {
        "W": "胜",
        "WIN": "胜",
        "胜": "胜",
        "D": "平",
        "DRAW": "平",
        "平": "平",
        "L": "负",
        "LOSS": "负",
        "负": "负",
    }
    tokens = [token for token in re.split(r"[\s,，、;/]+", raw.strip()) if token]
    return [mapping[token.upper()] for token in tokens if token.upper() in mapping][-6:]


def parse_injuries(raw: str) -> List[InjuryInfo]:
    """每行格式：球员|状态|影响值0-10|备注；普通文本也可直接输入。"""
    injuries: List[InjuryInfo] = []
    for index, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 3:
            try:
                impact = max(0.0, min(10.0, float(parts[2])))
            except ValueError:
                impact = 4.0
            injuries.append(
                InjuryInfo(
                    player=parts[0] or f"未命名球员{index}",
                    status=parts[1] or "情况待确认",
                    impact=impact,
                    note=parts[3] if len(parts) > 3 else "",
                )
            )
        else:
            injuries.append(InjuryInfo(f"伤停记录{index}", line, 4.0, "手动文本，影响值采用默认值"))
    return injuries


@st.cache_data(ttl=900, show_spinner=False)
def fetch_fixture_list(api_key: str, target_date: date, competition_codes: tuple[str, ...]) -> List[Fixture]:
    return FixtureFetcher(api_key=api_key).fetch(target_date, competition_codes)


@st.cache_data(ttl=900, show_spinner=False)
def build_fixture_features(api_key: str, fixture: Fixture) -> MatchFeatureResult:
    return FeatureEngine(api_key=api_key).build_for_fixture(fixture)


def get_selected_fixture() -> Optional[Fixture]:
    fixture_id = st.session_state.get("selected_fixture_id")
    return next(
        (fixture for fixture in st.session_state.available_fixtures if fixture.fixture_id == fixture_id),
        None,
    )


def apply_fixture(fixture: Fixture) -> None:
    st.session_state.home_name = fixture.home_team
    st.session_state.away_name = fixture.away_team
    st.session_state.match_date = fixture.kickoff_time.date()
    st.session_state.match_time = fixture.kickoff_time.time().replace(tzinfo=None)
    st.session_state.competition_code = fixture.competition_code
    st.session_state.neutral_venue = fixture.neutral_venue
    st.session_state.match_type = (
        MatchType.LEAGUE.value
        if fixture.competition_code in {"PL", "PD", "BL1", "SA", "FL1"}
        else MatchType.GROUP.value
    )
    st.session_state.qualification_context = f"{fixture.competition_name}比赛，具体出线/积分要求请按赛制复核。"
    st.session_state.auto_summary = (
        f"已选择：{fixture.display_name}。数据来源："
        f"{'Football-Data API' if fixture.source == 'football-data' else 'mock 回退数据'}。"
    )


def apply_feature_result(result: MatchFeatureResult) -> None:
    st.session_state.home_recent = " ".join(result.home.recent_results)
    st.session_state.away_recent = " ".join(result.away.recent_results)
    st.session_state.home_strength = result.home.basic_score
    st.session_state.away_strength = result.away.basic_score
    st.session_state.home_attack = result.home.attack_score
    st.session_state.away_attack = result.away.attack_score
    st.session_state.home_defense = result.home.defense_score
    st.session_state.away_defense = result.away.defense_score
    st.session_state.home_home_rating = int(round(result.home.venue_score))
    st.session_state.away_away_rating = int(round(result.away.venue_score))
    st.session_state.home_fitness = int(round(100 - result.home.fatigue_index))
    st.session_state.away_fitness = int(round(100 - result.away.fatigue_index))
    st.session_state.home_schedule_density = int(round(result.home.fatigue_index))
    st.session_state.away_schedule_density = int(round(result.away.fatigue_index))
    st.session_state.home_motivation = int(round(max(50, result.home.pressure_index)))
    st.session_state.away_motivation = int(round(max(50, result.away.pressure_index)))
    st.session_state.motivation_certainty = 65 if result.source.startswith("football-data") else 45
    st.session_state.standings_context = (
        f"{result.home.team_name}：第 {result.home.standing_position or '未知'} 名，"
        f"{result.home.standing_points if result.home.standing_points is not None else '未知'} 分；"
        f"{result.away.team_name}：第 {result.away.standing_position or '未知'} 名，"
        f"{result.away.standing_points if result.away.standing_points is not None else '未知'} 分。"
    )
    st.session_state.motivation_description = (
        f"积分压力指数：{result.home.team_name} {result.home.pressure_index:.1f}，"
        f"{result.away.team_name} {result.away.pressure_index:.1f}。该值由排名计算，需手动复核赛制背景。"
    )
    st.session_state.feature_result = result
    st.session_state.auto_summary = (
        f"自动基本面已生成（{result.source}）：主队 {result.home_basic_score:.2f}，"
        f"客队 {result.away_basic_score:.2f}，差值 {result.total_strength_diff:+.2f}，"
        f"倾向 {result.basic_trend}。所有字段仍可手动修正。"
    )


def build_team(prefix: str, name: str) -> TeamInfo:
    return TeamInfo(
        name=name.strip(),
        strength_rating=float(st.session_state[f"{prefix}_strength"]),
        recent_results=parse_recent_results(st.session_state[f"{prefix}_recent"]),
        attack_rating=float(st.session_state[f"{prefix}_attack"]),
        defense_rating=float(st.session_state[f"{prefix}_defense"]),
        key_player_status=st.session_state[f"{prefix}_key_status"].strip() or "暂无明确关键球员信息",
        key_player_availability=float(st.session_state[f"{prefix}_key_availability"]),
        injuries=parse_injuries(st.session_state[f"{prefix}_injuries"]),
        venue_performance=VenuePerformance(
            home_rating=float(st.session_state[f"{prefix}_home_rating"]),
            away_rating=float(st.session_state[f"{prefix}_away_rating"]),
            neutral_rating=float(st.session_state[f"{prefix}_neutral_rating"]),
        ),
        fitness_rating=float(st.session_state[f"{prefix}_fitness"]),
        tactical_style=st.session_state[f"{prefix}_tactics"].strip() or "战术信息待补充",
        schedule_density=float(st.session_state[f"{prefix}_schedule_density"]),
        weather_adaptability=float(st.session_state[f"{prefix}_weather_adapt"]),
        pitch_adaptability=float(st.session_state[f"{prefix}_pitch_adapt"]),
        injury_information_complete=bool(st.session_state[f"{prefix}_injury_complete"]),
    )


def render_team_inputs(prefix: str, label: str) -> None:
    st.markdown(f"#### {label}")
    st.text_input("近期战绩（胜/平/负，空格分隔）", key=f"{prefix}_recent")
    row1 = st.columns(3)
    row1[0].number_input("实力评级", 0.0, 100.0, key=f"{prefix}_strength")
    row1[1].number_input("进攻能力", 0.0, 100.0, key=f"{prefix}_attack")
    row1[2].number_input("防守能力", 0.0, 100.0, key=f"{prefix}_defense")
    st.text_area("关键球员状态", key=f"{prefix}_key_status", height=70)
    st.slider("关键球员可用度", 0, 100, key=f"{prefix}_key_availability")
    st.text_area(
        "伤停情况",
        key=f"{prefix}_injuries",
        height=90,
        help="每行可写：球员|状态|影响值0-10|备注；也可以输入普通文本。",
    )
    st.checkbox("伤停信息较完整", key=f"{prefix}_injury_complete")
    st.text_area("教练战术风格", key=f"{prefix}_tactics", height=70)
    row2 = st.columns(3)
    row2[0].slider("体能", 0, 100, key=f"{prefix}_fitness")
    row2[1].slider("赛程密度", 0, 100, key=f"{prefix}_schedule_density")
    row2[2].slider("天气适应", 0, 100, key=f"{prefix}_weather_adapt")
    row3 = st.columns(4)
    row3[0].slider("主场表现", 0, 100, key=f"{prefix}_home_rating")
    row3[1].slider("客场表现", 0, 100, key=f"{prefix}_away_rating")
    row3[2].slider("中立场表现", 0, 100, key=f"{prefix}_neutral_rating")
    row3[3].slider("场地适应", 0, 100, key=f"{prefix}_pitch_adapt")


def render_odds_inputs() -> None:
    st.markdown("#### 欧赔")
    opening = st.columns(3)
    opening[0].number_input("初盘主胜", 1.01, 30.0, 2.10, 0.01, key="eu_open_home")
    opening[1].number_input("初盘平局", 1.01, 30.0, 3.30, 0.01, key="eu_open_draw")
    opening[2].number_input("初盘客胜", 1.01, 30.0, 3.50, 0.01, key="eu_open_away")
    current = st.columns(3)
    current[0].number_input("即时主胜", 1.01, 30.0, 2.05, 0.01, key="eu_current_home")
    current[1].number_input("即时平局", 1.01, 30.0, 3.35, 0.01, key="eu_current_draw")
    current[2].number_input("即时客胜", 1.01, 30.0, 3.65, 0.01, key="eu_current_away")

    st.markdown("#### 亚盘（负数表示主队让球）")
    asian_open = st.columns(3)
    asian_open[0].number_input("初盘让球", -3.0, 3.0, -0.25, 0.25, key="ah_open_line")
    asian_open[1].number_input("初盘上盘水位", 0.50, 2.00, 0.92, 0.01, key="ah_open_upper")
    asian_open[2].number_input("初盘下盘水位", 0.50, 2.00, 0.94, 0.01, key="ah_open_lower")
    asian_current = st.columns(3)
    asian_current[0].number_input("即时让球", -3.0, 3.0, -0.25, 0.25, key="ah_current_line")
    asian_current[1].number_input("即时上盘水位", 0.50, 2.00, 0.88, 0.01, key="ah_current_upper")
    asian_current[2].number_input("即时下盘水位", 0.50, 2.00, 0.98, 0.01, key="ah_current_lower")

    st.markdown("#### 大小球")
    totals_open = st.columns(3)
    totals_open[0].number_input("初盘盘口", 0.0, 8.0, 2.50, 0.25, key="ou_open_line")
    totals_open[1].number_input("初盘大球水位", 0.50, 2.00, 0.92, 0.01, key="ou_open_over")
    totals_open[2].number_input("初盘小球水位", 0.50, 2.00, 0.94, 0.01, key="ou_open_under")
    totals_current = st.columns(3)
    totals_current[0].number_input("即时盘口", 0.0, 8.0, 2.50, 0.25, key="ou_current_line")
    totals_current[1].number_input("即时大球水位", 0.50, 2.00, 0.88, 0.01, key="ou_current_over")
    totals_current[2].number_input("即时小球水位", 0.50, 2.00, 0.98, 0.01, key="ou_current_under")
    st.text_input("数据来源/博彩公司", "手动输入", key="bookmaker")


def build_analysis_inputs() -> tuple[MatchInfo, OddsData]:
    home = build_team("home", st.session_state.home_name)
    away = build_team("away", st.session_state.away_name)
    kickoff = datetime.combine(st.session_state.match_date, st.session_state.match_time)
    match = MatchInfo(
        home_team=home,
        away_team=away,
        kickoff_time=kickoff,
        match_type=MatchType(st.session_state.match_type),
        neutral_venue=bool(st.session_state.neutral_venue),
        weather=st.session_state.weather.strip() or "天气信息待补充",
        venue=st.session_state.venue.strip() or "场地信息待补充",
        travel_distance_km=float(st.session_state.travel_distance),
        standings_context=st.session_state.standings_context.strip() or "积分形势待补充",
        qualification_context=st.session_state.qualification_context.strip() or "出线形势待补充",
        motivation_description=st.session_state.motivation_description.strip() or "战意信息待补充",
        home_motivation=float(st.session_state.home_motivation),
        away_motivation=float(st.session_state.away_motivation),
        motivation_certainty=float(st.session_state.motivation_certainty),
        head_to_head=HeadToHead(
            int(st.session_state.h2h_home),
            int(st.session_state.h2h_draw),
            int(st.session_state.h2h_away),
            st.session_state.h2h_description.strip(),
        ),
        is_final_group_round=bool(st.session_state.final_group_round),
    )
    odds = OddsData(
        european_opening=EuropeanOdds(
            st.session_state.eu_open_home,
            st.session_state.eu_open_draw,
            st.session_state.eu_open_away,
        ),
        european_current=EuropeanOdds(
            st.session_state.eu_current_home,
            st.session_state.eu_current_draw,
            st.session_state.eu_current_away,
        ),
        asian_opening=AsianHandicapOdds(
            st.session_state.ah_open_line,
            st.session_state.ah_open_upper,
            st.session_state.ah_open_lower,
        ),
        asian_current=AsianHandicapOdds(
            st.session_state.ah_current_line,
            st.session_state.ah_current_upper,
            st.session_state.ah_current_lower,
        ),
        totals_opening=TotalsOdds(
            st.session_state.ou_open_line,
            st.session_state.ou_open_over,
            st.session_state.ou_open_under,
        ),
        totals_current=TotalsOdds(
            st.session_state.ou_current_line,
            st.session_state.ou_current_over,
            st.session_state.ou_current_under,
        ),
        bookmaker=st.session_state.bookmaker.strip() or "手动输入",
        updated_at=datetime.now(),
    )
    return match, odds


st.set_page_config(page_title="个人足球预测分析工具", page_icon="⚽", layout="wide")
initialize_state()

st.title("个人足球预测分析工具")
st.caption("自动比赛 → 自动拉取数据 → 自动基本面评分 → 盘口分析 → 概率模型 → 风险分析。")
st.warning(
    "本工具仅用于足球数据分析、概率研究和学习，不构成投注建议，不提供任何收益承诺，"
    "也不保证预测结果准确。"
)

football_api_key = get_secret("FOOTBALL_DATA_API_KEY")
odds_api_key = get_secret("ODDS_API_KEY")
odds_fetcher = OddsFetcher(api_key=odds_api_key)
competition_labels = {
    "世界杯 World Cup": "WC",
    "英超 Premier League": "PL",
    "西甲 Primera Division": "PD",
    "德甲 Bundesliga": "BL1",
    "意甲 Serie A": "SA",
    "法甲 Ligue 1": "FL1",
    "欧冠 Champions League": "CL",
}

with st.sidebar:
    st.header("数据配置")
    selected_competition = st.selectbox(
        "手动模式赛事",
        list(competition_labels),
        index=list(competition_labels.values()).index(st.session_state.competition_code),
    )
    st.session_state.competition_code = competition_labels[selected_competition]
    if football_api_key:
        st.success("Football-Data API Key 已配置")
    else:
        st.info("未配置 Football-Data API Key，可完全手动使用。")
    if odds_fetcher.available:
        st.info("赔率接口凭据存在，但当前版本仍使用手动赔率。")
    else:
        st.info("赔率、亚盘和大小球保持手动输入。")
    st.divider()
    st.caption("API Key 不会写入代码或报告。")

st.subheader("自动比赛与基本面")
auto_filters = st.columns([1.0, 2.2, 1.0])
auto_filters[0].date_input("赛程日期", key="fixture_date")
default_labels = [label for label, code in competition_labels.items() if code in st.session_state.fixture_codes]
selected_labels = auto_filters[1].multiselect(
    "联赛筛选",
    list(competition_labels),
    default=default_labels,
    help="免费 API 的赛事覆盖取决于 Football-Data 套餐；失败时自动返回 mock 赛程。",
)
if auto_filters[2].button("自动获取比赛", type="primary", width="stretch"):
    codes = tuple(competition_labels[label] for label in selected_labels)
    if not codes:
        st.warning("请至少选择一个联赛。")
    else:
        with st.spinner("正在获取指定日期赛程……"):
            fixtures = fetch_fixture_list(football_api_key, st.session_state.fixture_date, codes)
        st.session_state.available_fixtures = fixtures
        st.session_state.selected_fixture_id = fixtures[0].fixture_id if fixtures else None
        st.session_state.feature_result = None
        source_text = "Football-Data API" if fixtures and fixtures[0].source == "football-data" else "mock 回退数据"
        st.session_state.auto_summary = f"已获取 {len(fixtures)} 场比赛，当前来源：{source_text}。"

if st.session_state.available_fixtures:
    fixture_map = {fixture.fixture_id: fixture for fixture in st.session_state.available_fixtures}
    recommendations = MatchRecommender().recommend(st.session_state.available_fixtures, limit=5)
    with st.expander("Top 5 推荐分析比赛", expanded=True):
        st.caption("推荐用于安排分析优先级，不是投注推荐；波动值为排名、强弱接近和赛程差异代理。")
        st.dataframe(
            [
                {
                    "比赛": item.fixture.display_name,
                    "类型": item.category,
                    "分析优先级": item.analysis_priority,
                    "强弱差": item.strength_gap,
                    "波动代理": item.volatility_proxy,
                }
                for item in recommendations
            ],
            width="stretch",
            hide_index=True,
        )
    st.selectbox(
        "选择比赛",
        options=list(fixture_map),
        format_func=lambda fixture_id: fixture_map[fixture_id].display_name,
        key="selected_fixture_id",
    )
    selected_fixture = get_selected_fixture()
    action_columns = st.columns(2)
    if action_columns[0].button("填入所选比赛", width="stretch"):
        if selected_fixture:
            apply_fixture(selected_fixture)
            st.rerun()
    if action_columns[1].button("自动生成基本面评分", type="primary", width="stretch"):
        if selected_fixture:
            with st.spinner("正在计算近期状态、攻防、主客场、疲劳和积分压力……"):
                feature_result = build_fixture_features(football_api_key, selected_fixture)
            apply_fixture(selected_fixture)
            apply_feature_result(feature_result)
            st.rerun()
else:
    st.info("选择日期和联赛后点击“自动获取比赛”。没有 API Key 时会自动使用模拟赛程。")

feature_result = st.session_state.get("feature_result")
if feature_result:
    metric_columns = st.columns(4)
    metric_columns[0].metric("主队基本面", f"{feature_result.home_basic_score:.2f}")
    metric_columns[1].metric("客队基本面", f"{feature_result.away_basic_score:.2f}")
    metric_columns[2].metric("强度差", f"{feature_result.total_strength_diff:+.2f}")
    metric_columns[3].metric("基本面倾向", feature_result.basic_trend)
    with st.expander("自动评分明细"):
        for explanation in feature_result.explanation:
            st.write(f"- {explanation}")
        st.caption(f"数据来源：{feature_result.source}。自动结果可在下方手动修正。")

st.divider()
st.subheader("比赛分析输入")

top = st.columns([1.2, 1.2, 0.9, 0.9])
top[0].text_input("主队", key="home_name")
top[1].text_input("客队", key="away_name")
top[2].date_input("比赛日期", key="match_date")
top[3].time_input("比赛时间", key="match_time")

match_row = st.columns(2)
match_row[0].selectbox("比赛类型", [item.value for item in MatchType], key="match_type")
match_row[1].checkbox("中立场", key="neutral_venue")

if st.session_state.auto_summary:
    st.success(st.session_state.auto_summary)

fundamental_tab, match_tab, odds_tab = st.tabs(["球队基本面", "比赛背景", "赔率与盘口"])
with fundamental_tab:
    teams = st.columns(2)
    with teams[0]:
        render_team_inputs("home", "主队数据")
    with teams[1]:
        render_team_inputs("away", "客队数据")

with match_tab:
    info_row = st.columns(3)
    info_row[0].text_input("天气", key="weather")
    info_row[1].text_input("场地", key="venue")
    info_row[2].number_input("客队旅行距离（km）", 0.0, 30000.0, step=50.0, key="travel_distance")
    st.text_area("积分形势", key="standings_context", height=90)
    st.text_area("出线形势", key="qualification_context", height=90)
    st.text_area("战意描述", key="motivation_description", height=90)
    motivation = st.columns(3)
    motivation[0].slider("主队战意", 0, 100, key="home_motivation")
    motivation[1].slider("客队战意", 0, 100, key="away_motivation")
    motivation[2].slider("战意信息确定性", 0, 100, key="motivation_certainty")
    st.checkbox("小组赛最后一轮", key="final_group_round")
    st.markdown("#### 历史交锋（可选）")
    h2h = st.columns(3)
    h2h[0].number_input("主队胜", 0, 100, 0, key="h2h_home")
    h2h[1].number_input("平局", 0, 100, 0, key="h2h_draw")
    h2h[2].number_input("客队胜", 0, 100, 0, key="h2h_away")
    st.text_input("交锋说明", "暂无可靠交锋样本", key="h2h_description")

with odds_tab:
    st.info("当前版本不自动请求付费赔率服务。请手动输入欧赔、亚盘和大小球数据。")
    render_odds_inputs()

st.divider()
if st.button("生成分析报告", type="primary", width="stretch"):
    try:
        match_info, odds_data = build_analysis_inputs()
        st.session_state.report = generate_report(match_info, odds_data)
    except ValueError as exc:
        st.error(f"输入数据校验失败：{exc}")
    except Exception as exc:
        st.error(f"生成报告失败：{exc}")

if st.session_state.report:
    st.subheader("分析报告")
    st.code(st.session_state.report, language=None)
    st.download_button(
        "下载报告（TXT）",
        data=st.session_state.report,
        file_name=f"football_report_{datetime.now():%Y%m%d_%H%M}.txt",
        mime="text/plain",
    )
