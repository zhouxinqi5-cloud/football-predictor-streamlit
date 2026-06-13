"""本地虚拟样例数据，不代表真实赛程、伤停或市场报价。"""

from datetime import datetime

from .models import (
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


def build_sample_data() -> tuple[MatchInfo, OddsData]:
    brazil = TeamInfo(
        name="巴西",
        strength_rating=89,
        recent_results=["胜", "胜", "平", "胜", "负", "胜"],
        attack_rating=90,
        defense_rating=84,
        key_player_status="核心攻击手状态良好，一名主力边锋出场存疑",
        key_player_availability=86,
        injuries=[
            InjuryInfo("主力边锋A", "出场存疑", 6.5, "肌肉不适"),
            InjuryInfo("替补后卫B", "缺阵", 2.0, "恢复期"),
        ],
        venue_performance=VenuePerformance(home_rating=91, away_rating=82, neutral_rating=87),
        fitness_rating=80,
        tactical_style="强调边路推进、前场压迫和快速转换",
        schedule_density=58,
        weather_adaptability=82,
        pitch_adaptability=86,
        injury_information_complete=True,
    )
    morocco = TeamInfo(
        name="摩洛哥",
        strength_rating=84,
        recent_results=["胜", "平", "胜", "胜", "平", "胜"],
        attack_rating=82,
        defense_rating=87,
        key_player_status="防线核心可出场，中场组织者刚刚伤愈",
        key_player_availability=82,
        injuries=[
            InjuryInfo("轮换中场C", "缺阵", 3.0, "脚踝伤势"),
            InjuryInfo("中场组织者D", "伤愈待定", 4.0, "比赛状态尚需观察"),
        ],
        venue_performance=VenuePerformance(home_rating=86, away_rating=81, neutral_rating=85),
        fitness_rating=84,
        tactical_style="防守结构紧凑，擅长中低位拦截与反击",
        schedule_density=48,
        weather_adaptability=88,
        pitch_adaptability=84,
        injury_information_complete=False,
    )
    match = MatchInfo(
        home_team=brazil,
        away_team=morocco,
        kickoff_time=datetime(2026, 7, 15, 20, 0),
        match_type=MatchType.KNOCKOUT,
        neutral_venue=True,
        weather="晴，预计 24°C，湿度中等（虚拟条件）",
        venue="国际体育场（虚拟场地）",
        travel_distance_km=6100,
        standings_context="淘汰赛不适用联赛积分",
        qualification_context="单场淘汰制，常规时间战平可能进入加时赛",
        motivation_description="双方晋级目标明确；巴西承受更高外部预期，摩洛哥具备反击取胜动力",
        home_motivation=92,
        away_motivation=94,
        motivation_certainty=82,
        head_to_head=HeadToHead(2, 0, 1, "近三次虚拟交锋：巴西2胜，摩洛哥1胜"),
        is_final_group_round=False,
    )
    odds = OddsData(
        european_opening=EuropeanOdds(home_win=1.82, draw=3.45, away_win=4.60),
        european_current=EuropeanOdds(home_win=1.90, draw=3.30, away_win=4.40),
        asian_opening=AsianHandicapOdds(handicap=-0.75, upper_water=0.98, lower_water=0.88),
        asian_current=AsianHandicapOdds(handicap=-0.50, upper_water=0.84, lower_water=1.02),
        totals_opening=TotalsOdds(line=2.50, over_water=0.95, under_water=0.91),
        totals_current=TotalsOdds(line=2.25, over_water=0.84, under_water=1.02),
        bookmaker="示例数据公司（虚拟）",
        updated_at=datetime(2026, 7, 14, 18, 30),
    )
    return match, odds
