"""Chinese display names for common national teams, clubs and competitions."""

from __future__ import annotations

import re


TEAM_NAME_MAP = {
    "Brazil": "巴西",
    "Morocco": "摩洛哥",
    "Argentina": "阿根廷",
    "France": "法国",
    "Germany": "德国",
    "Spain": "西班牙",
    "Portugal": "葡萄牙",
    "England": "英格兰",
    "Netherlands": "荷兰",
    "Japan": "日本",
    "South Korea": "韩国",
    "Korea Republic": "韩国",
    "Arsenal FC": "阿森纳",
    "Chelsea FC": "切尔西",
    "Manchester City FC": "曼城",
    "Manchester United FC": "曼联",
    "Liverpool FC": "利物浦",
    "Newcastle United FC": "纽卡斯尔联",
    "Tottenham Hotspur FC": "托特纳姆热刺",
    "Real Madrid CF": "皇家马德里",
    "FC Barcelona": "巴塞罗那",
    "Villarreal CF": "比利亚雷亚尔",
    "Sevilla FC": "塞维利亚",
    "FC Bayern München": "拜仁慕尼黑",
    "RB Leipzig": "RB莱比锡",
    "Bayer 04 Leverkusen": "勒沃库森",
    "Eintracht Frankfurt": "法兰克福",
    "FC Internazionale Milano": "国际米兰",
    "AS Roma": "罗马",
    "Juventus FC": "尤文图斯",
    "Atalanta BC": "亚特兰大",
    "Paris Saint-Germain FC": "巴黎圣日耳曼",
    "Olympique Lyonnais": "里昂",
    "AS Monaco FC": "摩纳哥",
    "Lille OSC": "里尔",
}


LEAGUE_NAME_MAP = {
    "Premier League": "英格兰足球超级联赛",
    "La Liga": "西班牙足球甲级联赛",
    "Primera Division": "西班牙足球甲级联赛",
    "Bundesliga": "德国足球甲级联赛",
    "Serie A": "意大利足球甲级联赛",
    "Ligue 1": "法国足球甲级联赛",
    "Champions League": "欧洲冠军联赛",
    "UEFA Champions League": "欧洲冠军联赛",
    "World Cup": "世界杯",
    "FIFA World Cup": "世界杯",
    "Manual Competition": "手动比赛",
}


def contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def display_team_name(name: str, mark_untranslated: bool = True) -> str:
    """Return a Chinese name, preserving user-entered Chinese names unchanged."""
    clean_name = (name or "").strip()
    if not clean_name:
        return "未知球队"
    if contains_chinese(clean_name):
        return clean_name
    translated = TEAM_NAME_MAP.get(clean_name)
    if translated:
        return translated
    return f"{clean_name}（未翻译）" if mark_untranslated else clean_name


def display_league_name(name: str, code: str = "") -> str:
    clean_name = (name or code or "未知赛事").strip()
    if contains_chinese(clean_name):
        return clean_name
    return LEAGUE_NAME_MAP.get(clean_name, f"{clean_name}（未翻译）")
