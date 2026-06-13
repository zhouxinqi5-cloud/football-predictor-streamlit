"""未来付费赔率服务的统一接口占位。"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


class OddsFetcher:
    """当前不调用付费服务；无 Key 或未配置供应商时均返回 None。"""

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None) -> None:
        self.api_key = (api_key or os.getenv("ODDS_API_KEY", "")).strip()
        self.provider = (provider or os.getenv("ODDS_API_PROVIDER", "")).strip()

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.provider)

    def fetch_match_odds(
        self,
        home_team: str,
        away_team: str,
        kickoff_time: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        del home_team, away_team, kickoff_time
        if not self.api_key:
            return None
        # 后续可在此按 provider 接入付费 Odds API，并转换为 OddsData。
        return None
