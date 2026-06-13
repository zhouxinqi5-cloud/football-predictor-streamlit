"""Deterministic mock fixtures and team histories for offline operation."""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Tuple
from zoneinfo import ZoneInfo

from football_ai.config import AsianOdds, EuropeanOdds, MatchFixture, OddsInput, TeamDataset, TotalsOdds


LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "CL": "Champions League",
    "WC": "World Cup",
}


MOCK_TEAMS: Dict[str, List[Tuple[str, str]]] = {
    "PL": [("Arsenal FC", "Chelsea FC"), ("Liverpool FC", "Newcastle United FC")],
    "PD": [("Real Madrid CF", "Villarreal CF"), ("FC Barcelona", "Sevilla FC")],
    "BL1": [("FC Bayern München", "RB Leipzig"), ("Bayer 04 Leverkusen", "Eintracht Frankfurt")],
    "SA": [("FC Internazionale Milano", "AS Roma"), ("Juventus FC", "Atalanta BC")],
    "FL1": [("Paris Saint-Germain FC", "Olympique Lyonnais"), ("AS Monaco FC", "Lille OSC")],
    "CL": [("Manchester City FC", "Real Madrid CF"), ("FC Bayern München", "Paris Saint-Germain FC")],
    "WC": [("Brazil", "Morocco"), ("Argentina", "France")],
}


class MockDataProvider:
    def __init__(self, timezone_name: str = "Asia/Shanghai") -> None:
        self.timezone = ZoneInfo(timezone_name)

    @staticmethod
    def _seed(value: str) -> int:
        return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)

    def fixtures(self, target_date: date, competition_codes: Iterable[str]) -> List[MatchFixture]:
        fixtures: List[MatchFixture] = []
        for code in competition_codes:
            code = code.upper()
            for index, (home, away) in enumerate(MOCK_TEAMS.get(code, [(f"{code} Home", f"{code} Away")])):
                randomizer = random.Random(self._seed(f"{target_date}:{code}:{home}:{away}"))
                kickoff = datetime.combine(
                    target_date,
                    time(18 + randomizer.randrange(5), 30 if randomizer.randrange(2) else 0),
                    tzinfo=self.timezone,
                )
                fixtures.append(
                    MatchFixture(
                        match_id=f"mock-{target_date}-{code}-{index}",
                        home_team=home,
                        away_team=away,
                        league=LEAGUES.get(code, code),
                        competition_code=code,
                        kickoff_time=kickoff,
                        neutral_ground=code == "WC",
                        source="mock",
                        home_team_id=1000 + index * 2 + 1,
                        away_team_id=1000 + index * 2 + 2,
                        home_position=randomizer.randint(1, 18),
                        away_position=randomizer.randint(1, 18),
                    )
                )
        return sorted(fixtures, key=lambda item: item.kickoff_time)

    def datasets(self, fixture: MatchFixture) -> Tuple[TeamDataset, TeamDataset]:
        randomizer = random.Random(self._seed(fixture.match_id))
        team_ids = (fixture.home_team_id or 1, fixture.away_team_id or 2)
        team_names = (fixture.home_team, fixture.away_team)
        hinted_positions = (fixture.home_position, fixture.away_position)
        positions = [hinted_positions[0] or randomizer.randint(1, 18), hinted_positions[1] or randomizer.randint(1, 18)]
        standings: Dict[int, Dict] = {}
        for team_id, name, position in zip(team_ids, team_names, positions):
            played = randomizer.randint(18, 30)
            ppg = max(0.7, 2.25 - position / 13 + randomizer.uniform(-0.15, 0.15))
            standings[team_id] = {
                "position": position,
                "team": {"id": team_id, "name": name},
                "playedGames": played,
                "points": round(ppg * played),
                "goalsFor": round((1.25 + (19 - position) / 24) * played),
                "goalsAgainst": round((0.75 + position / 17) * played),
            }
        for offset in range(3, 21):
            fake_id = 2000 + offset
            standings[fake_id] = {"position": offset, "team": {"id": fake_id, "name": f"Opponent {offset}"}}

        def history(team_id: int, opponent_start: int) -> List[Dict]:
            output = []
            days_ago = 3
            for index in range(20):
                is_home = index % 2 == 0
                opponent_id = opponent_start + index
                opponent_position = 1 + randomizer.randrange(20)
                standings[opponent_id] = {
                    "position": opponent_position,
                    "team": {"id": opponent_id, "name": f"Opponent {opponent_position}"},
                }
                team_goals = randomizer.choices([0, 1, 2, 3, 4], [16, 32, 29, 17, 6])[0]
                opponent_goals = randomizer.choices([0, 1, 2, 3], [24, 38, 26, 12])[0]
                played_at = fixture.kickoff_time - timedelta(days=days_ago)
                days_ago += randomizer.randint(2, 6)
                output.append(
                    {
                        "status": "FINISHED",
                        "utcDate": played_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "homeTeam": {"id": team_id if is_home else opponent_id},
                        "awayTeam": {"id": opponent_id if is_home else team_id},
                        "score": {
                            "fullTime": {
                                "home": team_goals if is_home else opponent_goals,
                                "away": opponent_goals if is_home else team_goals,
                            }
                        },
                    }
                )
            return output

        datasets = []
        for index, (team_id, name) in enumerate(zip(team_ids, team_names)):
            row = standings[team_id]
            datasets.append(
                TeamDataset(
                    team_id=team_id,
                    team_name=name,
                    position=row.get("position"),
                    points=row.get("points"),
                    played_games=row.get("playedGames"),
                    goals_for=row.get("goalsFor"),
                    goals_against=row.get("goalsAgainst"),
                    matches=history(team_id, 3000 + index * 100),
                    standings_by_team_id=dict(standings),
                    source="mock",
                )
            )
        return datasets[0], datasets[1]

    def odds(self, fixture: MatchFixture) -> OddsInput:
        """Build a deterministic neutral market baseline for offline demos."""
        randomizer = random.Random(self._seed(f"odds:{fixture.match_id}"))
        home_position = fixture.home_position or randomizer.randint(2, 16)
        away_position = fixture.away_position or randomizer.randint(2, 16)
        position_edge = max(-14, min(14, away_position - home_position))
        home_probability = max(0.24, min(0.68, 0.42 + position_edge * 0.018 + (0 if fixture.neutral_ground else 0.05)))
        draw_probability = max(0.20, min(0.32, 0.28 - abs(position_edge) * 0.003))
        away_probability = max(0.12, 1 - home_probability - draw_probability)
        total = home_probability + draw_probability + away_probability
        home_probability, draw_probability, away_probability = (
            home_probability / total,
            draw_probability / total,
            away_probability / total,
        )
        margin = 1.055
        opening = EuropeanOdds(
            round(1 / (home_probability * margin), 2),
            round(1 / (draw_probability * margin), 2),
            round(1 / (away_probability * margin), 2),
        )
        shift = randomizer.uniform(-0.018, 0.018)
        current_probs = [
            max(0.08, home_probability + shift),
            max(0.16, draw_probability - shift * 0.25),
            max(0.08, away_probability - shift * 0.75),
        ]
        current_total = sum(current_probs)
        current = EuropeanOdds(*[round(1 / (value / current_total * margin), 2) for value in current_probs])
        raw_line = -round(position_edge / 5 * 4) / 4 if position_edge else 0.0
        opening_line = max(-1.5, min(1.5, raw_line))
        line_move = randomizer.choice([-0.25, 0.0, 0.0, 0.25])
        current_line = max(-1.75, min(1.75, opening_line + line_move))
        opening_home_water = round(randomizer.uniform(0.88, 1.00), 2)
        current_home_water = round(max(0.78, min(1.08, opening_home_water + randomizer.uniform(-0.07, 0.07))), 2)
        total_line = randomizer.choice([2.25, 2.5, 2.75, 3.0])
        total_move = randomizer.choice([-0.25, 0.0, 0.0, 0.25])
        opening_over = round(randomizer.uniform(0.88, 0.99), 2)
        current_over = round(max(0.78, min(1.08, opening_over + randomizer.uniform(-0.06, 0.06))), 2)
        return OddsInput(
            european_opening=opening,
            european_current=current,
            asian_opening=AsianOdds(opening_line, opening_home_water, round(1.86 - opening_home_water, 2)),
            asian_current=AsianOdds(current_line, current_home_water, round(1.86 - current_home_water, 2)),
            totals_opening=TotalsOdds(total_line, opening_over, round(1.86 - opening_over, 2)),
            totals_current=TotalsOdds(total_line + total_move, current_over, round(1.86 - current_over, 2)),
            source="mock market baseline",
        )
