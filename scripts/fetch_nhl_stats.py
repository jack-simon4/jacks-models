"""
Fetch NHL team and goalie stats from the NHL Stats API.
Outputs:
  src/assets/NHL-Stats.csv   — Team,ShotsF,PP,ShotsA,S%
  src/assets/NHL-Goalies.csv — Player,GAA,Sv%,Team

Uses current season when teams average ≥5 games played; falls back to prior season.
"""

import csv
import os
import requests
from datetime import datetime

ASSETS         = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_OUTPUT   = os.path.join(ASSETS, 'NHL-Stats.csv')
GOALIES_OUTPUT = os.path.join(ASSETS, 'NHL-Goalies.csv')

NHL_BASE = 'https://api.nhle.com/stats/rest/en'

# NHL API abbreviation -> exact name used in NHL-Teams.csv
ABBREV_TO_NAME = {
    'ANA': 'Anaheim Ducks',
    'BOS': 'Boston Bruins',
    'BUF': 'Buffalo Sabres',
    'CGY': 'Calgary Flames',
    'CAR': 'Carolina Hurricanes',
    'CHI': 'Chicago Blackhawks',
    'COL': 'Colorado Avalanche',
    'CBJ': 'Columbus Blue Jackets',
    'DAL': 'Dallas Stars',
    'DET': 'Detroit Red Wings',
    'EDM': 'Edmonton Oilers',
    'FLA': 'Florida Panthers',
    'LAK': 'Los Angeles Kings',
    'MIN': 'Minnesota Wild',
    'MTL': 'Montréal Canadiens',
    'NSH': 'Nashville Predators',
    'NJD': 'New Jersey Devils',
    'NYI': 'New York Islanders',
    'NYR': 'New York Rangers',
    'OTT': 'Ottawa Senators',
    'PHI': 'Philadelphia Flyers',
    'PIT': 'Pittsburgh Penguins',
    'SJS': 'San Jose Sharks',
    'SEA': 'Seattle Kraken',
    'STL': 'St. Louis Blues',
    'TBL': 'Tampa Bay Lightning',
    'TOR': 'Toronto Maple Leafs',
    'UTA': 'Utah Mammoth',
    'VAN': 'Vancouver Canucks',
    'VGK': 'Vegas Golden Knights',
    'WSH': 'Washington Capitals',
    'WPG': 'Winnipeg Jets',
}


def current_season() -> tuple[str, str]:
    now = datetime.now()
    y   = now.year if now.month >= 10 else now.year - 1
    return f'{y}{y + 1}', f'{y - 1}{y}'


def _to_pct(val) -> float:
    """Return value as percentage (0–100). Handles both decimal (0.x) and pct (xx.x) forms."""
    try:
        v = float(val or 0)
        return round(v * 100, 2) if v < 2 else round(v, 2)
    except (TypeError, ValueError):
        return 0.0


def _api_get(endpoint: str, season: str) -> list[dict]:
    url    = f'{NHL_BASE}/{endpoint}'
    params = {
        'cayenneExp': f'seasonId={season} and gameTypeId=2',
        'sort':       'wins',
        'start':      '0',
        'limit':      '50',
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json().get('data', [])
        print(f'[NHL Stats] {endpoint} {season}: {len(data)} records')
        return data
    except Exception as exc:
        print(f'[NHL Stats] {endpoint} {season} error: {exc}')
        return []


def fetch_team_stats(season: str) -> list[dict]:
    return _api_get('team/summary', season)


def fetch_goalie_stats(season: str) -> list[dict]:
    url    = f'{NHL_BASE}/goalie/summary'
    params = {
        'cayenneExp': f'seasonId={season} and gameTypeId=2',
        'sort':       'gamesStarted',
        'start':      '0',
        'limit':      '100',
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json().get('data', [])
        print(f'[NHL Stats] goalie/summary {season}: {len(data)} goalies')
        return data
    except Exception as exc:
        print(f'[NHL Stats] goalie/summary {season} error: {exc}')
        return []


def _has_sufficient_data(data: list[dict]) -> bool:
    """Return True when current-season data has enough games to be statistically reliable."""
    if len(data) < 20:
        return False
    games = [float(t.get('gamesPlayed', 0) or 0) for t in data]
    avg_games = sum(games) / len(games) if games else 0
    print(f'[NHL Stats] Average games played: {avg_games:.1f} across {len(data)} entries')
    return avg_games >= 5.0


def write_team_stats(data: list[dict]) -> int:
    rows = []
    for t in data:
        abbrev = t.get('teamAbbrev', '')
        name   = ABBREV_TO_NAME.get(abbrev, t.get('teamFullName', abbrev))
        if not name:
            continue
        shots_f = round(float(t.get('shotsForPerGame',    0) or 0), 2)
        shots_a = round(float(t.get('shotsAgainstPerGame', 0) or 0), 2)
        pp      = _to_pct(t.get('ppPct',        t.get('powerPlayPct',  0)))
        s_raw = _to_pct(t.get('shootingPctg', t.get('shootingPct', 0)))
        if s_raw < 0.5 and shots_f > 0:  # API returned 0 — derive from goals/shots
            goals_f = float(t.get('goalsForPerGame', 0) or 0)
            s_raw = round(goals_f / shots_f * 100, 2) if goals_f > 0 else 8.0
        s_pct = s_raw
        if shots_f == 0:
            continue
        rows.append({'Team': name, 'ShotsF': shots_f, 'PP': pp, 'ShotsA': shots_a, 'S%': s_pct})

    rows.sort(key=lambda r: r['Team'])
    with open(STATS_OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Team', 'ShotsF', 'PP', 'ShotsA', 'S%'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'[NHL Stats] Wrote {len(rows)} teams -> {STATS_OUTPUT}')
    return len(rows)


def write_goalie_stats(data: list[dict]) -> int:
    rows = []
    for g in data:
        name = g.get('goalieFullName', '').strip()
        if not name:
            continue
        gaa = round(float(g.get('goalsAgainstAverage', 0) or 0), 3)
        sv  = float(g.get('savePct', g.get('savePctg', 0)) or 0)
        # Normalize: API may return decimal (0.917) or percentage (91.7)
        if sv > 1:
            sv = round(sv / 100, 4)
        else:
            sv = round(sv, 4)
        team_abbrev = str(g.get('teamAbbrevs', '') or '').split(',')[0].strip()
        team_name   = ABBREV_TO_NAME.get(team_abbrev, team_abbrev)
        if (gaa == 0 and sv == 0) or sv >= 1.0:
            continue
        rows.append({'Player': name, 'GAA': gaa, 'Sv%': sv, 'Team': team_name})

    rows.sort(key=lambda r: r['Player'])
    with open(GOALIES_OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Player', 'GAA', 'Sv%', 'Team'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'[NHL Stats] Wrote {len(rows)} goalies -> {GOALIES_OUTPUT}')
    return len(rows)


def main():
    cur_season, prior_season = current_season()
    print(f'[NHL Stats] Current season: {cur_season}  Prior: {prior_season}')

    # Team stats — prefer current season; fall back until avg ≥ 5 games played
    teams_data = fetch_team_stats(cur_season)
    if not _has_sufficient_data(teams_data):
        print(f'[NHL Stats] Using {prior_season} team stats (current season too sparse).')
        teams_data = fetch_team_stats(prior_season)
    write_team_stats(teams_data)

    # Goalie stats — same strategy
    goalies_data = fetch_goalie_stats(cur_season)
    if not _has_sufficient_data(goalies_data):
        print(f'[NHL Stats] Using {prior_season} goalie stats (current season too sparse).')
        goalies_data = fetch_goalie_stats(prior_season)
    write_goalie_stats(goalies_data)


if __name__ == '__main__':
    main()
