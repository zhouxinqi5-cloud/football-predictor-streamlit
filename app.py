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
        "match_date": date.today(),
        "home_recent": "胜 平 胜 负 胜",
        "away_recent": "平 胜 负 胜 平",
        "home_strength": 78.0,
        "away_strength": 76.0,
        "home_attack": 78.0,
        "away_attack": 75.0,
        "home_defense": 76.0,
        "away_defense": 74.0,
        "standings_context": "请手动填写积分排名，或使用自动获取功能。",
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
def fetch_fundamentals(
    api_key: str,
    competition_code: str,
    home_name: str,
    away_name: str,
    match_date: date,
):
    fetcher = FootballDataFetcher(api_key=api_key, min_request_interval=0.15)
    return fetcher.get_match_fundamentals(
        competition_code=competition_code,
        home_team_name=home_name,
        away_team_name=away_name,
        match_date=match_date,
    )


def apply_automatic_data(data: Any) -> None:
    st.session_state.home_recent = data.home.recent_form_text
    st.session_state.away_recent = data.away.recent_form_text
    st.session_state.home_strength = data.home.strength_rating
    st.session_state.away_strength = data.away.strength_rating
    st.session_state.home_attack = data.home.attack_rating
    st.session_state.away_attack = data.away.attack_rating
    st.session_state.home_defense = data.home.defense_rating
    st.session_state.away_defense = data.away.defense_rating
    st.session_state.standings_context = (
        f"{data.home.team_name}：{data.home.standing_text}；"
        f"{data.away.team_name}：{data.away.standing_text}。"
    )
    fixture_text = "已匹配到当日赛程" if data.matching_fixture else "未匹配到当日赛程"
    st.session_state.auto_summary = (
        f"自动数据已更新。{fixture_text}。近5场："
        f"{data.home.team_name} {data.home.recent_form_text}，进 {data.home.recent_goals_for} / "
        f"失 {data.home.recent_goals_against}；"
        f"{data.away.team_name} {data.away.recent_form_text}，进 {data.away.recent_goals_for} / "
        f"失 {data.away.recent_goals_against}。"
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
    st.slider("关键球员可用度", 0, 100, 80, key=f"{prefix}_key_availability")
    st.text_area(
        "伤停情况",
        key=f"{prefix}_injuries",
        height=90,
        help="每行可写：球员|状态|影响值0-10|备注；也可以输入普通文本。",
    )
    st.checkbox("伤停信息较完整", value=False, key=f"{prefix}_injury_complete")
    st.text_area("教练战术风格", key=f"{prefix}_tactics", height=70)
    row2 = st.columns(3)
    row2[0].slider("体能", 0, 100, 75, key=f"{prefix}_fitness")
    row2[1].slider("赛程密度", 0, 100, 50, key=f"{prefix}_schedule_density")
    row2[2].slider("天气适应", 0, 100, 70, key=f"{prefix}_weather_adapt")
    row3 = st.columns(4)
    row3[0].slider("主场表现", 0, 100, 75, key=f"{prefix}_home_rating")
    row3[1].slider("客场表现", 0, 100, 70, key=f"{prefix}_away_rating")
    row3[2].slider("中立场表现", 0, 100, 70, key=f"{prefix}_neutral_rating")
    row3[3].slider("场地适应", 0, 100, 70, key=f"{prefix}_pitch_adapt")


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
st.caption("基本面为主，盘口和指数为辅。自动数据只覆盖赛程、积分、近期战绩和进失球。")
st.warning(
    "本工具仅用于足球数据分析、概率研究和学习，不构成投注建议，不提供任何收益承诺，"
    "也不保证预测结果准确。"
)

football_api_key = get_secret("FOOTBALL_DATA_API_KEY")
odds_api_key = get_secret("ODDS_API_KEY")
odds_fetcher = OddsFetcher(api_key=odds_api_key)

with st.sidebar:
    st.header("数据配置")
    competitions = {
        "英超 Premier League": "PL",
        "西甲 Primera Division": "PD",
        "德甲 Bundesliga": "BL1",
        "意甲 Serie A": "SA",
        "法甲 Ligue 1": "FL1",
        "欧冠 Champions League": "CL",
        "世界杯 World Cup": "WC",
    }
    selected_competition = st.selectbox(
        "赛事",
        list(competitions),
        index=list(competitions.values()).index(st.session_state.competition_code),
    )
    st.session_state.competition_code = competitions[selected_competition]
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

top = st.columns([1.2, 1.2, 0.9, 0.9])
top[0].text_input("主队", key="home_name")
top[1].text_input("客队", key="away_name")
top[2].date_input("比赛日期", key="match_date")
top[3].time_input("比赛时间", value=time(20, 0), key="match_time")

match_row = st.columns(3)
match_row[0].selectbox("比赛类型", [item.value for item in MatchType], key="match_type")
match_row[1].checkbox("中立场", value=False, key="neutral_venue")

if match_row[2].button("自动获取基本面数据", use_container_width=True, type="secondary"):
    if not football_api_key:
        st.warning("未配置 Football-Data API Key。请继续使用下方手动输入，或配置 Key 后重试。")
    elif not st.session_state.home_name.strip() or not st.session_state.away_name.strip():
        st.warning("请先填写主队和客队名称。")
    else:
        try:
            with st.spinner("正在获取赛程、积分榜和近期比赛……"):
                automatic_data = fetch_fundamentals(
                    football_api_key,
                    st.session_state.competition_code,
                    st.session_state.home_name,
                    st.session_state.away_name,
                    st.session_state.match_date,
                )
            apply_automatic_data(automatic_data)
            st.rerun()
        except FootballDataError as exc:
            st.error(f"自动获取失败：{exc} 请检查赛事和球队英文名称，或继续手动输入。")
        except Exception as exc:  # 页面不能因外部服务异常而中断手动流程
            st.error(f"自动获取发生未预期错误：{exc}。请继续手动输入。")

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
    info_row[0].text_input("天气", "天气信息待确认", key="weather")
    info_row[1].text_input("场地", "比赛场地待确认", key="venue")
    info_row[2].number_input("客队旅行距离（km）", 0.0, 30000.0, 0.0, 50.0, key="travel_distance")
    st.text_area("积分形势", key="standings_context", height=90)
    st.text_area("出线形势", "请根据赛制手动填写。", key="qualification_context", height=90)
    st.text_area("战意描述", "请结合积分、轮换和赛程手动判断。", key="motivation_description", height=90)
    motivation = st.columns(3)
    motivation[0].slider("主队战意", 0, 100, 75, key="home_motivation")
    motivation[1].slider("客队战意", 0, 100, 75, key="away_motivation")
    motivation[2].slider("战意信息确定性", 0, 100, 55, key="motivation_certainty")
    st.checkbox("小组赛最后一轮", value=False, key="final_group_round")
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
if st.button("生成分析报告", type="primary", use_container_width=True):
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
