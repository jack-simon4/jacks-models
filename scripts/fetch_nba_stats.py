"""
Fetch NBA team efficiency stats from ESPN box scores and write NBA-Stats.csv.

For each game played so far this season, fetch the ESPN box score and aggregate:
  FGA, OReb, TO, FTA, PTS for both teams.

Then compute per team:
  Poss      = FGA - OReb + TO + 0.44 * FTA       (Dean Oliver formula)
  OffRtg    = (PTS / Poss) * 100
  DefRtg    = (Opp_PTS / Opp_Poss) * 100
  Pace      = (Poss + Opp_Poss) / 2              (avg per game)
  adjT      = Pace / league_avg_pace

Column mapping written to CSV:
  Off        = season OffRtg / 100
  oLastThree = last-3-game OffRtg / 100
  oHome      = home OffRtg / 100
  oAway      = road OffRtg / 100
  adjO       = Off (same)
  Def        = season DefRtg / 100
  dLastThree = last-3-game DefRtg / 100
  dHome      = home DefRtg / 100
  dAway      = road DefRtg / 100
  adjD       = Def (same)
  Tempo      = Pace
  adjT       = Pace / league_avg_pace
"""

import csv
import os
import sys
import time
import requests
from collections import defaultdict
from datetime import date, timedelta, datetime

ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
OUTPUT = os.path.join(ASSETS, 'NBA-Stats.csv')

# ESPN abbreviation → CSV team name (must match NBA-Teams.csv / NBA-Stats.csv)
ABBREV_TO_NAME = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GS':  'Golden State Warriors', 'GSW': 'Golden State Warriors',
    'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'Los Angeles Clippers', 'LAL': 'Los Angeles Lakers',
    'MEM': 'Memphis Grizzlies', 'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks',
    'MIN': 'Minnesota Timberwolves',
    'NO':  'New Orleans Pelicans', 'NOP': 'New Orleans Pelicans',
    'NY':  'New York Knicks',      'NYK': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic',
    'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings',
    'SA':  'San Antonio Spurs',   'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors',
    'UTA': 'Utah Jazz',           'UTAH': 'Utah Jazz',
    'WAS': 'Washington Wizards',  'WSH': 'Washington Wizards',
}

SEASON_START = date(2026, 10, 22)   # adjust if season starts on a different date


def _get(url: str, retries: int = 3) -> dict | None:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200:
                return r.json()
        except Exception as exc:
            print(f'  attempt {attempt}: {exc}')
        if attempt < retries:
            time.sleep(3 * attempt)
    return None


def _parse_stat(stats_list: list, name: str) -> float:
    """Extract a numeric value from a list of ESPN box score stat dicts."""
    for s in stats_list:
        if s.get('name') == name:
            raw = s.get('displayValue', '')
            # Some are "FGM-FGA" format; take first number
            part = raw.split('-')[0].strip()
            try:
                return float(part)
            except ValueError:
                return 0.0
    return 0.0


def _compute_poss(fga: float, oreb: float, to: float, fta: float) -> float:
    return fga - oreb + to + 0.44 * fta


def fetch_game_ids(season_dates: list[str]) -> list[tuple[str, str, str]]:
    """Return list of (game_id, date_str, status) for all games in the date range."""
    games = []
    seen = set()
    for d in season_dates:
        data = _get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}')
        if not data:
            continue
        for event in data.get('events', []):
            gid = event.get('id')
            if not gid or gid in seen:
                continue
            comp = (event.get('competitions') or [{}])[0]
            status = comp.get('status', {}).get('type', {}).get('name', '')
            if status == 'STATUS_FINAL':
                seen.add(gid)
                games.append((gid, d, status))
        time.sleep(0.2)
    print(f'[NBA Stats] Found {len(games)} completed games')
    return games


def fetch_box_score(game_id: str) -> list[dict] | None:
    """Return list of team box dicts: {name, abbrev, pts, fga, oreb, to, fta, is_home}."""
    data = _get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}')
    if not data:
        return None
    teams_out = []
    for comp in data.get('boxscore', {}).get('teams', []):
        abbrev = comp.get('team', {}).get('abbreviation', '')
        name   = ABBREV_TO_NAME.get(abbrev)
        if not name:
            print(f'  [NBA Stats] Unknown abbrev: {abbrev}')
            return None
        stats  = comp.get('statistics', [])

        def _s(n): return _parse_stat(stats, n)

        fgm = _s('fieldGoalsMade-fieldGoalsAttempted')    # returns FGM
        fga_raw = stats[0].get('displayValue', '0-0') if stats else '0-0'
        # FGA is in "FGM-FGA" field — parse properly
        fga = oreb = to = fta = fgm_val = threePM = ftm = 0.0
        for s in stats:
            n = s.get('name', '')
            v = s.get('displayValue', '0')
            if n == 'fieldGoalsMade-fieldGoalsAttempted':
                parts = v.split('-')
                fgm_val = float(parts[0]) if parts else 0
                fga     = float(parts[1]) if len(parts) > 1 else 0
            elif n == 'threePointFieldGoalsMade-threePointFieldGoalsAttempted':
                parts = v.split('-')
                threePM = float(parts[0]) if parts else 0
            elif n == 'freeThrowsMade-freeThrowsAttempted':
                parts = v.split('-')
                ftm = float(parts[0]) if parts else 0
                fta = float(parts[1]) if len(parts) > 1 else 0
            elif n == 'offensiveRebounds':
                try:
                    oreb = float(v)
                except ValueError:
                    oreb = 0
            elif n == 'turnovers':
                try:
                    to = float(v)
                except ValueError:
                    to = 0

        pts = 2 * fgm_val + threePM + ftm   # = 2*FGM + extra for 3s + FTM

        # homeAway is on the competition competitor, not on boxscore.teams
        # We re-fetch from the event competitions if needed — skip for now, handle via game structure
        teams_out.append({
            'name':  name,
            'abbrev': abbrev,
            'pts':   pts,
            'fga':   fga,
            'oreb':  oreb,
            'to':    to,
            'fta':   fta,
        })

    # Determine home/away from scoreboard competition competitors
    comp_data = data.get('header', {}).get('competitions', [{}])[0]
    for c in comp_data.get('competitors', []):
        a = c.get('team', {}).get('abbreviation', '')
        resolved = ABBREV_TO_NAME.get(a)
        for t in teams_out:
            if t['name'] == resolved:
                t['is_home'] = (c.get('homeAway') == 'home')

    if len(teams_out) == 2:
        return teams_out
    return None


def aggregate_stats(game_ids: list[tuple[str, str, str]]) -> dict:
    """
    Returns {team_name: {'all': BoxAgg, 'home': BoxAgg, 'away': BoxAgg, 'last3': BoxAgg}}
    BoxAgg = {'pts', 'fga', 'oreb', 'to', 'fta', 'opp_pts', 'opp_fga', 'opp_oreb', 'opp_to', 'opp_fta', 'games'}
    """
    def new_agg():
        return defaultdict(float)

    data = defaultdict(lambda: {k: new_agg() for k in ('all', 'home', 'away', 'last3')})
    team_games = defaultdict(list)   # team_name → list of (date, agg_slot)

    total = len(game_ids)
    for i, (gid, date_str, _) in enumerate(game_ids):
        box = fetch_box_score(gid)
        if not box or len(box) != 2:
            continue
        t0, t1 = box[0], box[1]
        # Ensure is_home is set
        if 'is_home' not in t0:
            t0['is_home'] = True
            t1['is_home'] = False

        for t, opp in [(t0, t1), (t1, t0)]:
            name  = t['name']
            slot  = 'home' if t.get('is_home') else 'away'
            for bucket in ('all', slot):
                agg = data[name][bucket]
                agg['pts']     += t['pts']
                agg['fga']     += t['fga']
                agg['oreb']    += t['oreb']
                agg['to']      += t['to']
                agg['fta']     += t['fta']
                agg['opp_pts'] += opp['pts']
                agg['opp_fga'] += opp['fga']
                agg['opp_oreb']+= opp['oreb']
                agg['opp_to']  += opp['to']
                agg['opp_fta'] += opp['fta']
                agg['games']   += 1
            team_games[name].append((date_str, t, opp))

        time.sleep(0.15)
        if (i + 1) % 10 == 0:
            print(f'[NBA Stats] Box scores fetched: {i + 1}/{total}')

    # Build last-3-games aggregates
    for team_name, game_list in team_games.items():
        game_list.sort(key=lambda x: x[0])
        last3 = game_list[-3:]
        agg = data[team_name]['last3']
        for _, t, opp in last3:
            agg['pts']     += t['pts']
            agg['fga']     += t['fga']
            agg['oreb']    += t['oreb']
            agg['to']      += t['to']
            agg['fta']     += t['fta']
            agg['opp_pts'] += opp['pts']
            agg['opp_fga'] += opp['fga']
            agg['opp_oreb']+= opp['oreb']
            agg['opp_to']  += opp['to']
            agg['opp_fta'] += opp['fta']
            agg['games']   += 1

    return data


def compute_ratings(agg: dict) -> tuple[float, float, float]:
    """Returns (OffRtg/100, DefRtg/100, Pace) from an aggregation bucket."""
    g   = agg['games']
    if g == 0:
        return 1.0, 1.0, 100.0
    poss     = _compute_poss(agg['fga'], agg['oreb'], agg['to'], agg['fta'])
    opp_poss = _compute_poss(agg['opp_fga'], agg['opp_oreb'], agg['opp_to'], agg['opp_fta'])
    if poss == 0 or opp_poss == 0:
        return 1.0, 1.0, 100.0
    off_rtg  = (agg['pts'] / poss) * 100
    def_rtg  = (agg['opp_pts'] / opp_poss) * 100
    pace     = ((poss + opp_poss) / 2) / g
    return round(off_rtg / 100, 6), round(def_rtg / 100, 6), round(pace, 2)


def main():
    today     = date.today()
    all_dates = []
    d = SEASON_START
    while d <= today:
        all_dates.append(d.strftime('%Y%m%d'))
        d += timedelta(days=1)

    print(f'[NBA Stats] Scanning {len(all_dates)} dates ({SEASON_START} to {today})')
    game_ids = fetch_game_ids(all_dates)

    if not game_ids:
        print('[NBA Stats] No completed games found — aborting.')
        sys.exit(1)

    print(f'[NBA Stats] Fetching box scores for {len(game_ids)} games...')
    team_data = aggregate_stats(game_ids)

    if not team_data:
        print('[NBA Stats] No team data aggregated — aborting.')
        sys.exit(1)

    # League-average pace (for adjT)
    all_paces = []
    for name, buckets in team_data.items():
        _, _, pace = compute_ratings(buckets['all'])
        all_paces.append(pace)
    lg_pace = sum(all_paces) / len(all_paces) if all_paces else 100.0
    print(f'[NBA Stats] League-average Pace: {lg_pace:.2f}')

    fieldnames = ['Team','Off','oLastThree','oHome','oAway','adjO',
                  'Def','dLastThree','dHome','dAway','adjD','Tempo','adjT']
    csv_rows = []

    for team_name in sorted(team_data):
        buckets = team_data[team_name]
        off,   def_r, pace = compute_ratings(buckets['all'])
        oL3,   dL3,  _    = compute_ratings(buckets.get('last3', defaultdict(float)))
        oH,    dH,   _    = compute_ratings(buckets.get('home',  defaultdict(float)))
        oA,    dA,   _    = compute_ratings(buckets.get('away',  defaultdict(float)))

        # Fall back to season average when split has no games
        if buckets.get('last3', {}).get('games', 0) == 0:
            oL3, dL3 = off, def_r
        if buckets.get('home',  {}).get('games', 0) == 0:
            oH, dH = off, def_r
        if buckets.get('away',  {}).get('games', 0) == 0:
            oA, dA = off, def_r

        csv_rows.append({
            'Team':        team_name,
            'Off':         off,
            'oLastThree':  oL3,
            'oHome':       oH,
            'oAway':       oA,
            'adjO':        off,
            'Def':         def_r,
            'dLastThree':  dL3,
            'dHome':       dH,
            'dAway':       dA,
            'adjD':        def_r,
            'Tempo':       pace,
            'adjT':        round(pace / lg_pace, 6),
        })

    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f'[NBA Stats] Wrote {len(csv_rows)} teams -> {OUTPUT}')


if __name__ == '__main__':
    main()
