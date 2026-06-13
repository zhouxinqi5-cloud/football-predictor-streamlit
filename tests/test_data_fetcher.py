"""外部数据客户端的无网络测试。"""

import unittest
from datetime import date

from football_predictor.data_fetcher import FootballDataError, FootballDataFetcher
from football_predictor.odds_fetcher import OddsFetcher


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, headers, params, timeout):
        self.calls.append(
            {"url": url, "headers": headers, "params": params, "timeout": timeout}
        )
        return FakeResponse(self.payload)


class DataFetcherTests(unittest.TestCase):
    def test_missing_api_key_uses_manual_fallback_error(self):
        fetcher = FootballDataFetcher(api_key="")
        with self.assertRaisesRegex(FootballDataError, "手动输入"):
            fetcher.get_standings("PL")

    def test_fixture_request_uses_auth_header_and_inclusive_end_date(self):
        session = FakeSession({"matches": []})
        fetcher = FootballDataFetcher(api_key="secret", session=session)
        result = fetcher.get_fixtures("PL", date(2026, 6, 13), date(2026, 6, 13))

        self.assertEqual(result, [])
        call = session.calls[0]
        self.assertEqual(call["headers"]["X-Auth-Token"], "secret")
        self.assertEqual(call["params"]["dateFrom"], "2026-06-13")
        self.assertEqual(call["params"]["dateTo"], "2026-06-14")

    def test_team_summary_calculates_recent_goals_and_results(self):
        fetcher = FootballDataFetcher(api_key="secret")
        team = {"id": 1, "name": "Home FC"}
        table = [
            {
                "position": 2,
                "team": {"id": 1},
                "playedGames": 10,
                "won": 6,
                "draw": 2,
                "lost": 2,
                "points": 20,
                "goalsFor": 18,
                "goalsAgainst": 9,
            }
        ]
        matches = [
            {
                "homeTeam": {"id": 1},
                "awayTeam": {"id": 2},
                "score": {"fullTime": {"home": 2, "away": 0}},
            },
            {
                "homeTeam": {"id": 3},
                "awayTeam": {"id": 1},
                "score": {"fullTime": {"home": 1, "away": 1}},
            },
        ]
        summary = fetcher._build_team_summary(team, table, matches)

        self.assertEqual(summary.recent_results, ["胜", "平"])
        self.assertEqual(summary.recent_goals_for, 3)
        self.assertEqual(summary.recent_goals_against, 1)
        self.assertEqual(summary.position, 2)

    def test_odds_fetcher_returns_none_without_key(self):
        self.assertIsNone(OddsFetcher(api_key="").fetch_match_odds("A", "B"))


if __name__ == "__main__":
    unittest.main()
