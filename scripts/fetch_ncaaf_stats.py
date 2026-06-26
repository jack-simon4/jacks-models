"""
Fetch NCAAF team stats from the College Football Data API and update NCAAF-Stats.csv.

Requires a free API key from https://collegefootballdata.com/key stored as
the CFBD_API_KEY GitHub secret (or environment variable).

Computes all 18 columns used by the scoreboard model:
  SOS, oRating, dRating,
  Yds/Play, Last3, wYds/Play,
  D Yds/Play, Last3, wD Yds/Play,
  Yds/Point, Last3, wYds/Point,
  D Yds/Point, Last3, wD Yds/Point,
  PlaysGame, dPlaysGame, HomeAdv

wYds/Play = 0.65 * season + 0.35 * last3  (recency-weighted)
oRating   = team_pts_per_game / national_avg_pts  (>1 = above average offense)
dRating   = team_pts_allowed_per_game / national_avg_pts  (>1 = below average defense)

Runs via GitHub Actions on Sundays (captures Saturday games).
"""

import math
import os
import sys
import time
from datetime import date

import pandas as pd
import requests

API_KEY = os.environ.get('CFBD_API_KEY', '')
BASE = 'https://api.collegefootballdata.com'

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
OUTPUT = os.path.join(ASSETS, 'NCAAF-Stats.csv')

# ── Season year (NCAAF season starts in August) ──────────────────────────────
_today = date.today()
SEASON_YEAR = _today.year if _today.month >= 8 else _today.year - 1
PRIOR_YEAR  = SEASON_YEAR - 1

# How many games of current-season data before we fully trust it over the prior
BLEND_FULL_GAMES = 8

# Weight of last-3-games stats in the wYds/* columns
W_RECENT = 0.35
W_SEASON = 1.0 - W_RECENT

# ── Our CSV team names → cfbd school names ───────────────────────────────────
# Only entries that differ need to be listed here.
TEAM_NAME_MAP = {
    'App State':       'Appalachian State',
    'Arizona St':      'Arizona State',
    'Arkansas St':     'Arkansas State',
    'Ball St':         'Ball State',
    'Boise St':        'Boise State',
    'C Michigan':      'Central Michigan',
    'Coastal Car':     'Coastal Carolina',
    'Colorado St':     'Colorado State',
    'E Carolina':      'East Carolina',
    'E Michigan':      'Eastern Michigan',
    'Florida Intl':    'Florida International',
    'Florida St':      'Florida State',
    'Fresno St':       'Fresno State',
    'Georgia So':      'Georgia Southern',
    'Georgia St':      'Georgia State',
    "Hawai'i":         'Hawaii',
    'J Madison':       'James Madison',
    'Jacksonville St': 'Jacksonville State',
    'Kansas St':       'Kansas State',
    'Kent St':         'Kent State',
    'Louisiana':       'Louisiana',
    'Miami OH':        'Miami (OH)',
    'Middle Tenn':     'Middle Tennessee',
    'Mississippi':     'Ole Miss',
    'Mississippi St':  'Mississippi State',
    'Missouri St':     'Missouri State',   # FCS — likely absent from API
    'N Illinois':      'Northern Illinois',
    'N Texas':         'North Texas',
    'NC State':        'NC State',
    'New Mexico St':   'New Mexico State',
    'Penn St':         'Penn State',
    'S Alabama':       'South Alabama',
    'S Florida':       'South Florida',
    'Sam Houston':     'Sam Houston',
    'San Diego St':    'San Diego State',
    'San Jose St':     'San Jose State',
    'Southern Miss':   'Southern Miss',
    'Texas A&M':       'Texas A&M',
    'Texas St':        'Texas State',
    'UAB':             'UAB',
    'UCF':             'UCF',
    'UConn':           'Connecticut',
    'UL Monroe':       'Louisiana Monroe',
    'UMass':           'Massachusetts',
    'UNLV':            'UNLV',
    'Utah St':         'Utah State',
    'UTEP':            'UTEP',
    'UTSA':            'UTSA',
    'Virginia Tech':   'Virginia Tech',
    'W Kentucky':      'Western Kentucky',
    'W Michigan':      'Western Michigan',
    'Washington St':   'Washington State',
}

# Reverse map: cfbd name → our CSV name
CFBD_TO_CSV = {v: k for k, v in TEAM_NAME_MAP.items()}


def _api(endpoint: str, params: dict = None, retries: int = 3) -> list:
    """GET from cfbd API with retry on 429."""
    headers = {'Authorization': f'Bearer {API_KEY}'}
    for attempt in range(retries):
        try:
            resp = requests.get(f'{BASE}{endpoint}', headers=headers,
                                params=params or {}, timeout=30)
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == retries - 1:
                raise
            time.sleep(3)
    return []


def _safe(val, fallback: float) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else fallback
    except (TypeError, ValueError):
        return fallback


def _parse_attempts(s: str) -> int:
    """Parse '22-29' → 29, or '45' → 45."""
    if '-' in str(s):
        return int(str(s).split('-')[1])
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def fetch_game_stats(year: int) -> dict:
    """
    Fetch per-game stats for all teams.
    Returns {csv_team_name: [{'date': ..., 'off': {...}, 'def': {...}}, ...]}
    where off/def are stat dicts for that team's offense/defense in each game.
    """
    print(f'[NCAAF] Fetching {year} per-game stats...')
    raw = _api('/games/teams', {'year': year, 'seasonType': 'regular'})
    if not raw:
        return {}

    # Build: {cfbd_school: [(game_id, homeAway, points, stat_dict), ...]}
    school_games: dict[str, list] = {}
    game_dates: dict[int, str] = {}

    for game in raw:
        game_id = game.get('id', 0)
        for team_entry in game.get('teams', []):
            school = team_entry.get('school', '')
            points = _safe(team_entry.get('points'), 0)
            stats_raw = {s['category']: s['stat']
                         for s in team_entry.get('stats', [])}

            total_yds   = _safe(stats_raw.get('totalYards', 0), 0)
            plays       = _safe(stats_raw.get('plays', 0), 1)
            rush_yds    = _safe(stats_raw.get('rushingYards', 0), 0)
            rush_att    = _safe(stats_raw.get('rushingAttempts', 0), 1)
            pass_yds    = _safe(stats_raw.get('netPassingYards', 0), 0)
            pass_att    = _parse_attempts(stats_raw.get('completionAttempts', '0-0'))

            g = {
                'game_id':  game_id,
                'points':   points,
                'total_yds': total_yds,
                'plays':     max(plays, 1),
                'rush_yds':  rush_yds,
                'rush_att':  max(rush_att, 1),
                'pass_yds':  pass_yds,
                'pass_att':  max(pass_att, 1),
                'yds_play':  total_yds / max(plays, 1),
            }
            school_games.setdefault(school, []).append(g)

    # Convert cfbd names to CSV names
    result = {}
    for cfbd_name, games in school_games.items():
        csv_name = CFBD_TO_CSV.get(cfbd_name, cfbd_name)
        result[csv_name] = games

    return result


def fetch_sp_ratings(year: int) -> dict:
    """
    Fetch SP+ ratings.
    Returns {csv_team_name: {'sos': float}}
    """
    print(f'[NCAAF] Fetching {year} SP+ ratings...')
    raw = _api('/ratings/sp', {'year': year})
    result = {}
    for entry in raw:
        cfbd_name = entry.get('team', '')
        csv_name = CFBD_TO_CSV.get(cfbd_name, cfbd_name)
        sos = _safe(entry.get('sos'), 0.0)
        result[csv_name] = {'sos': sos}
    return result


def compute_stats(game_data: list[dict]) -> dict:
    """
    Given a team's list of game dicts, compute season and last-3 averages.
    """
    if not game_data:
        return {}

    n = len(game_data)

    def avg(key):
        vals = [g[key] for g in game_data if key in g]
        return sum(vals) / len(vals) if vals else 0.0

    def avg_last3(key):
        recent = game_data[-3:]
        vals = [g[key] for g in recent if key in g]
        return sum(vals) / len(vals) if vals else avg(key)

    return {
        'games':        n,
        'pts_for_pg':   avg('points'),
        'yds_play':     avg('yds_play'),
        'yds_play_l3':  avg_last3('yds_play'),
        'yds_pt':       None,  # filled after pts computed
        'plays_pg':     avg('plays'),
    }


def compute_def_stats(opp_game_data: list[dict]) -> dict:
    """Given a list of opponent game dicts (what opponents did vs this team)."""
    if not opp_game_data:
        return {}

    n = len(opp_game_data)

    def avg(key):
        vals = [g[key] for g in opp_game_data if key in g]
        return sum(vals) / len(vals) if vals else 0.0

    def avg_last3(key):
        recent = opp_game_data[-3:]
        vals = [g[key] for g in recent if key in g]
        return sum(vals) / len(vals) if vals else avg(key)

    return {
        'pts_against_pg':   avg('points'),
        'd_yds_play':       avg('yds_play'),
        'd_yds_play_l3':    avg_last3('yds_play'),
        'd_plays_pg':       avg('plays'),
    }


def build_opponent_views(all_game_data: dict) -> dict:
    """
    Build {csv_team: [opponent_game_dicts, ...]} from per-team game data.
    Each game appears for both teams; we cross-reference to get opponent stats.
    """
    # Map game_id → {school → game_dict}
    by_game: dict[int, dict] = {}
    for team, games in all_game_data.items():
        for g in games:
            gid = g.get('game_id', 0)
            by_game.setdefault(gid, {})[team] = g

    # For each team, collect the opponent's stats from each game
    opp_views: dict[str, list] = {}
    for team, games in all_game_data.items():
        opp_list = []
        for g in games:
            gid = g.get('game_id', 0)
            opponents = {k: v for k, v in by_game.get(gid, {}).items() if k != team}
            for opp_g in opponents.values():
                opp_list.append(opp_g)
        opp_views[team] = opp_list

    return opp_views


def load_prior() -> pd.DataFrame | None:
    if not os.path.exists(OUTPUT):
        return None
    try:
        return pd.read_csv(OUTPUT, index_col='Team')
    except Exception:
        return None


def prior_val(prior: pd.DataFrame | None, team: str, col: str,
              fallback: float) -> float:
    if prior is not None and team in prior.index:
        try:
            v = float(prior.loc[team, col])
            if math.isfinite(v):
                return v
        except Exception:
            pass
    return fallback


def build():
    if not API_KEY:
        print('[NCAAF] CFBD_API_KEY not set — skipping.')
        sys.exit(0)

    # Load existing CSV team list (preserves team order)
    prior = load_prior()
    if prior is None:
        print('[NCAAF] No existing NCAAF-Stats.csv found; cannot determine team list.')
        sys.exit(1)
    teams_in_csv = list(prior.index)

    # Try current season; fall back to prior year in off-season
    game_data = fetch_game_stats(SEASON_YEAR)
    using_prior_year = False
    if not game_data:
        print(f'[NCAAF] No {SEASON_YEAR} game data — trying {PRIOR_YEAR}.')
        game_data = fetch_game_stats(PRIOR_YEAR)
        using_prior_year = True
        if not game_data:
            print('[NCAAF] No data available. Aborting.')
            sys.exit(1)

    sp_year = PRIOR_YEAR if using_prior_year else SEASON_YEAR
    sp_ratings = fetch_sp_ratings(sp_year)
    opp_views  = build_opponent_views(game_data)

    # Compute national averages for oRating / dRating
    all_pts_for     = [g['points'] for glist in game_data.values() for g in glist]
    national_avg    = sum(all_pts_for) / len(all_pts_for) if all_pts_for else 30.0

    # Default league-average values (used when data is absent)
    LG = {
        'yds_play':   5.8,
        'd_yds_play': 5.8,
        'yds_pt':     14.5,
        'd_yds_pt':   14.5,
        'plays_pg':   68.0,
        'd_plays_pg': 68.0,
        'home_adv':   2.5,
        'sos':        0.0,
        'o_rating':   1.0,
        'd_rating':   1.0,
    }

    rows = []
    for csv_team in teams_in_csv:
        off_games = game_data.get(csv_team, [])
        def_games = opp_views.get(csv_team, [])

        gp = len(off_games)
        # Blend weight: 0 = all prior, 1 = all current
        w = 1.0 if using_prior_year else min(gp / BLEND_FULL_GAMES, 1.0)

        if off_games:
            off = compute_stats(off_games)
            def_ = compute_def_stats(def_games)
        else:
            off = {}
            def_ = {}

        def cur_off(key, fb):
            return _safe(off.get(key), fb) if off else fb

        def cur_def(key, fb):
            return _safe(def_.get(key), fb) if def_ else fb

        # ── Season stats ─────────────────────────────────────────────────────
        pts_for     = cur_off('pts_for_pg', national_avg)
        pts_against = cur_def('pts_against_pg', national_avg)
        yds_play    = cur_off('yds_play',    LG['yds_play'])
        yds_play_l3 = cur_off('yds_play_l3', yds_play)
        plays_pg    = cur_off('plays_pg',    LG['plays_pg'])

        d_yds_play    = cur_def('d_yds_play',    LG['d_yds_play'])
        d_yds_play_l3 = cur_def('d_yds_play_l3', d_yds_play)
        d_plays_pg    = cur_def('d_plays_pg',     LG['d_plays_pg'])

        yds_pt   = (yds_play * plays_pg) / pts_for   if pts_for   > 0 else LG['yds_pt']
        d_yds_pt = (d_yds_play * d_plays_pg) / pts_against if pts_against > 0 else LG['d_yds_pt']

        # Rough last-3 approximation for Yds/Pt (use last3 yds/play ratio)
        yds_pt_l3   = yds_pt   * (yds_play_l3   / max(yds_play,   0.1))
        d_yds_pt_l3 = d_yds_pt * (d_yds_play_l3 / max(d_yds_play, 0.1))

        # Weighted stats
        w_yds_play   = W_SEASON * yds_play   + W_RECENT * yds_play_l3
        wd_yds_play  = W_SEASON * d_yds_play + W_RECENT * d_yds_play_l3
        w_yds_pt     = W_SEASON * yds_pt     + W_RECENT * yds_pt_l3
        wd_yds_pt    = W_SEASON * d_yds_pt   + W_RECENT * d_yds_pt_l3

        # Ratings
        o_rating = pts_for     / national_avg if national_avg > 0 else 1.0
        d_rating = pts_against / national_avg if national_avg > 0 else 1.0

        # SOS from SP+
        sos = sp_ratings.get(csv_team, {}).get('sos', 0.0)

        # Home advantage: use prior if available (limited by single-season sample)
        home_adv = prior_val(prior, csv_team, 'HomeAdv', LG['home_adv'])

        # ── Blend with prior CSV ─────────────────────────────────────────────
        def b(col, cur_val):
            p = prior_val(prior, csv_team, col, cur_val)
            return round(w * cur_val + (1 - w) * p, 3)

        rows.append({
            'Team':        csv_team,
            'SOS':         round(sos, 1),
            'oRating':     b('oRating',     o_rating),
            'dRating':     b('dRating',     d_rating),
            'Yds/Play':    b('Yds/Play',    round(yds_play, 1)),
            'Last 3':      round(yds_play_l3, 1),
            'wYds/Play':   b('wYds/Play',   round(w_yds_play, 3)),
            'D Yds/Play':  b('D Yds/Play',  round(d_yds_play, 1)),
            'Last 3.1':    round(d_yds_play_l3, 1),
            'wD Yds/Play': b('wD Yds/Play', round(wd_yds_play, 3)),
            'Yds/Point':   b('Yds/Point',   round(yds_pt, 1)),
            'Last 3.2':    round(yds_pt_l3, 1),
            'wYds/Point':  b('wYds/Point',  round(w_yds_pt, 3)),
            'D Yds/Point': b('D Yds/Point', round(d_yds_pt, 1)),
            'Last 3.3':    round(d_yds_pt_l3, 1),
            'wD Yds/Point': b('wD Yds/Point', round(wd_yds_pt, 3)),
            'PlaysGame':   b('PlaysGame',   round(plays_pg, 1)),
            'dPlaysGame':  b('dPlaysGame',  round(d_plays_pg, 1)),
            'HomeAdv':     round(home_adv, 2),
        })
        status = f'{gp} games, blend {w:.0%}' if not using_prior_year else 'prior year (full season)'
        print(f'  {csv_team}: {status}')

    if not rows:
        print('[NCAAF] No rows generated. Aborting.')
        sys.exit(1)

    # Write with the original CSV column header names
    df = pd.DataFrame(rows)
    # Rename duplicate "Last 3" columns back to match the original CSV header
    df.columns = [
        'Team', 'SOS', 'oRating', 'dRating',
        'Yds/Play', 'Last 3', 'wYds/Play',
        'D Yds/Play', 'Last 3', 'wD Yds/Play',
        'Yds/Point', 'Last 3', 'wYds/Point',
        'D Yds/Point', 'Last 3', 'wD Yds/Point',
        'PlaysGame', 'dPlaysGame', 'HomeAdv',
    ]
    df.to_csv(OUTPUT, index=False)
    print(f'[NCAAF] Wrote {len(rows)} teams → {OUTPUT}')


if __name__ == '__main__':
    build()
