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

# Games needed before we trust current-season data exclusively.
BLEND_FULL_GAMES = 3

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
    'Iowa St':         'Iowa State',
    'J Madison':       'James Madison',
    'Jacksonville St': 'Jacksonville State',
    'Kansas St':       'Kansas State',
    'Kennesaw St':     'Kennesaw State',
    'Kent St':         'Kent State',
    'Louisiana':       'Louisiana',
    'Miami OH':        'Miami (OH)',
    'Michigan St':     'Michigan State',
    'Middle Tenn':     'Middle Tennessee',
    'Mississippi':     'Ole Miss',
    'Mississippi St':  'Mississippi State',
    'Missouri St':     'Missouri State',
    'N Illinois':      'Northern Illinois',
    'N Texas':         'North Texas',
    'NC State':        'NC State',
    'New Mexico St':   'New Mexico State',
    'Ohio St':         'Ohio State',
    'Oklahoma St':     'Oklahoma State',
    'Oregon St':       'Oregon State',
    'Penn St':         'Penn State',
    'S Alabama':       'South Alabama',
    'S Florida':       'South Florida',
    'Sam Houston':     'Sam Houston State',
    'San Diego St':    'San Diego State',
    'San Jose St':     'San Jose State',
    'Southern Miss':   'Southern Mississippi',
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


def _weeks_played(year: int) -> int:
    """Estimate how many regular-season weeks have completed for a given year."""
    season_start = date(year, 8, 24)   # NCAAF week 1 typically starts around Aug 24
    if _today < season_start:
        return 0
    return min((_today - season_start).days // 7 + 1, 16)


def fetch_game_stats(year: int) -> dict:
    """
    Fetch per-game stats for all teams by iterating week-by-week.
    Returns {csv_team_name: [game_dict, ...]}

    Note: /games/teams requires 'week' in addition to 'year' — omitting it
    causes a 400 Bad Request. We loop weeks 1..N where N is either the
    estimated current week (for the current season) or 16 (for a completed
    prior season).
    """
    max_week = _weeks_played(year) if year == SEASON_YEAR else 16
    if max_week == 0:
        print(f'[NCAAF] {year} season has not started yet.')
        return {}

    print(f'[NCAAF] Fetching {year} per-game stats (weeks 1–{max_week})...')
    school_games: dict[str, list] = {}

    for week in range(1, max_week + 1):
        # Try without classification first (broader), then with fbs filter
        params_attempts = [
            {'year': year, 'week': week, 'seasonType': 'regular'},
            {'year': year, 'week': week},
        ]
        raw = []
        for params in params_attempts:
            try:
                raw = _api('/games/teams', params)
                if raw:
                    break
            except Exception as exc:
                print(f'[NCAAF] WARNING: {year} w{week} params={params} error: {exc}')
        if not raw:
            continue

        for game in raw:
            game_id = game.get('id', 0)
            teams_key = 'teams' if 'teams' in game else None
            if teams_key is None:
                # Log first unexpected game structure for diagnosis
                if len(school_games) == 0:
                    print(f'[NCAAF] Unexpected game structure (keys: {list(game.keys())[:10]})')
                continue
            for team_entry in game.get('teams', []):
                school = team_entry.get('school', '') or team_entry.get('team', '')
                if not school:
                    continue
                points = _safe(team_entry.get('points'), 0)
                stats_raw = {s['category']: s['stat']
                             for s in team_entry.get('stats', [])}

                total_yds = _safe(stats_raw.get('totalYards', 0), 0)
                rush_yds  = _safe(stats_raw.get('rushingYards', 0), 0)
                rush_att  = int(_safe(stats_raw.get('rushingAttempts', 0), 0))
                pass_yds  = _safe(stats_raw.get('netPassingYards', 0), 0)
                pass_att  = _parse_attempts(stats_raw.get('completionAttempts', '0-0'))

                # CFBD does not return a bare 'plays' category; compute from
                # rush + pass attempts which gives total offensive plays.
                total_plays = max(rush_att + pass_att, 1)

                # Use yardsPerPlay stat when available; otherwise derive it.
                ypp_stat = _safe(stats_raw.get('yardsPerPlay', 0), 0)
                if 2.0 < ypp_stat < 12.0:
                    yds_play = ypp_stat
                else:
                    yds_play = total_yds / total_plays

                g = {
                    'game_id':   game_id,
                    'points':    points,
                    'total_yds': total_yds,
                    'plays':     total_plays,
                    'rush_yds':  rush_yds,
                    'rush_att':  max(rush_att, 1),
                    'pass_yds':  pass_yds,
                    'pass_att':  max(pass_att, 1),
                    'yds_play':  yds_play,
                }
                school_games.setdefault(school, []).append(g)

        time.sleep(0.2)  # stay well under rate limits

    if not school_games:
        print(f'[NCAAF] No game data returned for {year}.')
        return {}

    # Log sample of raw API team names for diagnosis
    sample_names = list(school_games.keys())[:10]
    print(f'[NCAAF] {year}: API returned {len(school_games)} schools. Sample: {sample_names}')

    # Convert cfbd names to CSV names
    result = {}
    unmatched = []
    for cfbd_name, games in school_games.items():
        csv_name = CFBD_TO_CSV.get(cfbd_name, cfbd_name)
        result[csv_name] = games
        if cfbd_name not in CFBD_TO_CSV and cfbd_name not in result:
            unmatched.append(cfbd_name)

    if unmatched:
        print(f'[NCAAF] {year}: {len(unmatched)} names passed through unchanged (no explicit mapping): {unmatched[:15]}')
    print(f'[NCAAF] {year}: got data for {len(result)} teams after name conversion.')
    return result


def fetch_sp_ratings(year: int) -> dict:
    """
    Fetch SP+ ratings.
    Returns {csv_team_name: {'sos': float}}
    SP+ may not be published early in the season — returns {} on failure.
    """
    print(f'[NCAAF] Fetching {year} SP+ ratings...')
    try:
        raw = _api('/ratings/sp', {'year': year})
    except Exception as exc:
        print(f'[NCAAF] WARNING: SP+ ratings not available for {year}: {exc}')
        return {}
    result = {}
    for entry in raw:
        cfbd_name = entry.get('team', '')
        csv_name = CFBD_TO_CSV.get(cfbd_name, cfbd_name)
        sos = _safe(entry.get('sos'), 0.0)
        result[csv_name] = {'sos': sos}
    print(f'[NCAAF] SP+ ratings loaded for {len(result)} teams.')
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


def blend_weight(gp: int) -> float:
    """Return the weight to place on current-season stats vs prior-season stats.
    3+ games → 100% current season.
    1–2 games → current season still outweighs prior (college rosters turn over heavily).
    0 games → fall back entirely to prior year."""
    if gp >= 3:
        return 1.0
    if gp == 2:
        return 0.80
    if gp == 1:
        return 0.60
    return 0.0


def compute_team_stats(off_games: list, def_games: list, national_avg: float, lg: dict) -> dict:
    """Compute all stats for one team from their offense/defense game lists."""
    if not off_games:
        return {}
    off  = compute_stats(off_games)
    def_ = compute_def_stats(def_games) if def_games else {}

    def co(key, fb): return _safe(off.get(key),  fb)
    def cd(key, fb): return _safe(def_.get(key), fb) if def_ else fb

    pts_for     = co('pts_for_pg',    national_avg)
    pts_against = cd('pts_against_pg', national_avg)
    yds_play    = co('yds_play',    lg['yds_play'])
    yds_play_l3 = co('yds_play_l3', yds_play)
    plays_pg    = co('plays_pg',    lg['plays_pg'])

    d_yds_play    = cd('d_yds_play',    lg['d_yds_play'])
    d_yds_play_l3 = cd('d_yds_play_l3', d_yds_play)
    d_plays_pg    = cd('d_plays_pg',    lg['d_plays_pg'])

    yds_pt   = (yds_play   * plays_pg)   / pts_for     if pts_for     > 0 else lg['yds_pt']
    d_yds_pt = (d_yds_play * d_plays_pg) / pts_against if pts_against > 0 else lg['d_yds_pt']

    yds_pt_l3   = yds_pt   * (yds_play_l3   / max(yds_play,   0.1))
    d_yds_pt_l3 = d_yds_pt * (d_yds_play_l3 / max(d_yds_play, 0.1))

    return {
        'pts_for':     pts_for,
        'pts_against': pts_against,
        'yds_play':    yds_play,    'yds_play_l3':   yds_play_l3,
        'd_yds_play':  d_yds_play,  'd_yds_play_l3': d_yds_play_l3,
        'yds_pt':      yds_pt,      'yds_pt_l3':     yds_pt_l3,
        'd_yds_pt':    d_yds_pt,    'd_yds_pt_l3':   d_yds_pt_l3,
        'plays_pg':    plays_pg,    'd_plays_pg':    d_plays_pg,
        'games':       len(off_games),
    }


def build():
    if not API_KEY:
        print('[NCAAF] CFBD_API_KEY not set — skipping.')
        sys.exit(0)

    # Load existing CSV for team list and HomeAdv (which we preserve across seasons)
    prior_csv = load_prior()
    if prior_csv is None:
        print('[NCAAF] No existing NCAAF-Stats.csv found; cannot determine team list.')
        sys.exit(1)
    teams_in_csv = list(prior_csv.index)

    # Always fetch current-season game data
    print(f'[NCAAF] Fetching {SEASON_YEAR} (current) and {PRIOR_YEAR} (baseline) data...')
    cur_game_data   = fetch_game_stats(SEASON_YEAR)
    prior_game_data = fetch_game_stats(PRIOR_YEAR)

    if not cur_game_data and not prior_game_data:
        print('[NCAAF] No game data available from API. Aborting.')
        sys.exit(1)

    # Check how many CSV teams are actually matched in cur_game_data.
    # If very few match (API data present but team names don't align),
    # treat it as off-season and rely on prior year.
    csv_matches_cur = sum(1 for t in teams_in_csv if cur_game_data.get(t))
    csv_matches_prior = sum(1 for t in teams_in_csv if prior_game_data.get(t) if prior_game_data)
    print(f'[NCAAF] CSV team matches — {SEASON_YEAR}: {csv_matches_cur}/{len(teams_in_csv)}, '
          f'{PRIOR_YEAR}: {csv_matches_prior}/{len(teams_in_csv)}')

    # Fall back to off-season mode if current data doesn't match CSV names
    off_season = csv_matches_cur < 5
    if off_season and cur_game_data:
        print(f'[NCAAF] {SEASON_YEAR} data returned but <5 CSV teams matched — '
              f'treating as off-season, using {PRIOR_YEAR} only.')
    elif off_season:
        print(f'[NCAAF] No {SEASON_YEAR} games yet — using {PRIOR_YEAR} only.')

    # SP+ ratings: prefer current season
    sp_ratings = fetch_sp_ratings(SEASON_YEAR if not off_season else PRIOR_YEAR)

    cur_opp_views   = build_opponent_views(cur_game_data)   if cur_game_data   else {}
    prior_opp_views = build_opponent_views(prior_game_data) if prior_game_data else {}

    # National avg from current season if available, else prior
    ref_data = cur_game_data if cur_game_data else prior_game_data
    all_pts  = [g['points'] for glist in ref_data.values() for g in glist]
    national_avg = sum(all_pts) / len(all_pts) if all_pts else 30.0

    LG = {
        'yds_play':   5.8,  'd_yds_play': 5.8,
        'yds_pt':     14.5, 'd_yds_pt':   14.5,
        'plays_pg':   68.0, 'd_plays_pg': 68.0,
        'home_adv':   2.5,  'sos':        0.0,
    }

    # ── Pass 1: raw oRating/dRating and cached stats for every team ──────────
    raw_o:    dict[str, float] = {}
    raw_d:    dict[str, float] = {}
    stats_cache: dict[str, dict] = {}

    for csv_team in teams_in_csv:
        cur_off   = cur_game_data.get(csv_team, [])
        cur_def   = cur_opp_views.get(csv_team, [])
        prior_off = prior_game_data.get(csv_team, []) if prior_game_data else []
        prior_def = prior_opp_views.get(csv_team, []) if prior_opp_views else []
        gp = len(cur_off)
        w  = 0.0 if off_season else blend_weight(gp)
        cur_s   = compute_team_stats(cur_off,   cur_def,   national_avg, LG) if cur_off   else {}
        prior_s = compute_team_stats(prior_off, prior_def, national_avg, LG) if prior_off else {}
        pts_for     = w * cur_s.get('pts_for',     national_avg) + (1 - w) * prior_s.get('pts_for',     national_avg)
        pts_against = w * cur_s.get('pts_against', national_avg) + (1 - w) * prior_s.get('pts_against', national_avg)
        raw_o[csv_team] = pts_for     / national_avg if national_avg > 0 else 1.0
        raw_d[csv_team] = pts_against / national_avg if national_avg > 0 else 1.0
        stats_cache[csv_team] = {'gp': gp, 'w': w, 'cur_s': cur_s, 'prior_s': prior_s}

    # ── Build game_id → teams map (enables finding each team's opponents) ─────
    game_to_teams: dict[int, list[str]] = {}
    if not off_season:
        for t, games in cur_game_data.items():
            for g in games:
                game_to_teams.setdefault(g['game_id'], []).append(t)

    # ── SOS-adjust oRating/dRating based on opponent quality ──────────────────
    # adj = raw / (0.5 + 0.5 * avg_opp_factor)  ← 50% dampening prevents overcorrection
    # oRating: divide by avg opponent dRating (facing good defenses inflates raw score)
    # dRating: divide by avg opponent oRating (facing weak offenses deflates raw dRating)
    def _sos_adj(raw: float, opp_factor: float) -> float:
        return raw / max(0.5 + 0.5 * opp_factor, 0.1)

    adj_o:   dict[str, float] = {}
    adj_d:   dict[str, float] = {}
    adj_sos: dict[str, float] = {}

    for csv_team in teams_in_csv:
        gp = stats_cache[csv_team]['gp']
        if off_season or gp == 0:
            adj_o[csv_team]   = raw_o.get(csv_team, 1.0)
            adj_d[csv_team]   = raw_d.get(csv_team, 1.0)
            adj_sos[csv_team] = 0.0
            continue
        opp_o_vals, opp_d_vals = [], []
        for g in cur_game_data.get(csv_team, []):
            for opp in game_to_teams.get(g['game_id'], []):
                if opp != csv_team and opp in raw_o:
                    opp_o_vals.append(raw_o[opp])
                    opp_d_vals.append(raw_d[opp])
        if opp_o_vals:
            avg_opp_o = sum(opp_o_vals) / len(opp_o_vals)
            avg_opp_d = sum(opp_d_vals) / len(opp_d_vals)
            adj_o[csv_team]   = _sos_adj(raw_o.get(csv_team, 1.0), avg_opp_d)
            adj_d[csv_team]   = _sos_adj(raw_d.get(csv_team, 1.0), avg_opp_o)
            adj_sos[csv_team] = round(avg_opp_o, 3)
        else:
            adj_o[csv_team]   = raw_o.get(csv_team, 1.0)
            adj_d[csv_team]   = raw_d.get(csv_team, 1.0)
            adj_sos[csv_team] = 0.0

    # ── Pass 2: write final rows using SOS-adjusted oRating/dRating ───────────
    rows = []
    for csv_team in teams_in_csv:
        cache   = stats_cache[csv_team]
        gp      = cache['gp']
        w       = cache['w']
        cur_s   = cache['cur_s']
        prior_s = cache['prior_s']

        def blend(key, fallback, _w=w, _c=cur_s, _p=prior_s):
            return _w * _c.get(key, fallback) + (1 - _w) * _p.get(key, fallback)

        yds_play      = blend('yds_play',      LG['yds_play'])
        yds_play_l3   = blend('yds_play_l3',   yds_play)
        d_yds_play    = blend('d_yds_play',    LG['d_yds_play'])
        d_yds_play_l3 = blend('d_yds_play_l3', d_yds_play)
        yds_pt        = blend('yds_pt',        LG['yds_pt'])
        yds_pt_l3     = blend('yds_pt_l3',     yds_pt)
        d_yds_pt      = blend('d_yds_pt',      LG['d_yds_pt'])
        d_yds_pt_l3   = blend('d_yds_pt_l3',   d_yds_pt)
        plays_pg      = blend('plays_pg',      LG['plays_pg'])
        d_plays_pg    = blend('d_plays_pg',    LG['d_plays_pg'])

        w_yds_play  = W_SEASON * yds_play   + W_RECENT * yds_play_l3
        wd_yds_play = W_SEASON * d_yds_play + W_RECENT * d_yds_play_l3
        w_yds_pt    = W_SEASON * yds_pt     + W_RECENT * yds_pt_l3
        wd_yds_pt   = W_SEASON * d_yds_pt   + W_RECENT * d_yds_pt_l3

        o_rating = adj_o.get(csv_team, 1.0)
        d_rating = adj_d.get(csv_team, 1.0)
        sos      = adj_sos.get(csv_team, 0.0)
        home_adv = prior_val(prior_csv, csv_team, 'HomeAdv', LG['home_adv'])

        rows.append({
            'Team':         csv_team,
            'SOS':          round(sos, 1),
            'oRating':      round(o_rating,   3),
            'dRating':      round(d_rating,   3),
            'Yds/Play':     round(yds_play,   1),
            'Last 3':       round(yds_play_l3, 1),
            'wYds/Play':    round(w_yds_play, 3),
            'D Yds/Play':   round(d_yds_play, 1),
            'Last 3.1':     round(d_yds_play_l3, 1),
            'wD Yds/Play':  round(wd_yds_play, 3),
            'Yds/Point':    round(yds_pt,     1),
            'Last 3.2':     round(yds_pt_l3,  1),
            'wYds/Point':   round(w_yds_pt,   3),
            'D Yds/Point':  round(d_yds_pt,   1),
            'Last 3.3':     round(d_yds_pt_l3, 1),
            'wD Yds/Point': round(wd_yds_pt,  3),
            'PlaysGame':    round(plays_pg,   1),
            'dPlaysGame':   round(d_plays_pg, 1),
            'HomeAdv':      round(home_adv,   2),
        })

        if off_season:
            status = f'off-season, {PRIOR_YEAR} only'
        elif gp == 0:
            status = f'no {SEASON_YEAR} games, using {PRIOR_YEAR}'
        elif gp >= BLEND_FULL_GAMES:
            status = f'{gp} games, 100% {SEASON_YEAR} (SOS-adj)'
        else:
            status = f'{gp} game(s), {w:.0%} {SEASON_YEAR} / {1-w:.0%} {PRIOR_YEAR} (SOS-adj)'
        print(f'  {csv_team}: {status}')

    if not rows:
        print('[NCAAF] No rows generated. Aborting.')
        sys.exit(1)

    df = pd.DataFrame(rows)
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
