"""
Fetch NFL team stats from nfl_data_py and update NFL-Stats.csv.

Aggregates play-by-play and schedule data for the current season into
the 14 stat columns used by the scoreboard model. Blends current-season
numbers with the prior season when few games have been played so
Week 1–4 predictions don't rely entirely on a handful of games.

Runs via GitHub Actions on Monday/Tuesday nights after games complete.
"""

import math
import os
import sys
from datetime import date

import pandas as pd

try:
    import nfl_data_py as nfl
except ImportError:
    print('[NFL] nfl-data-py not installed; skipping.')
    sys.exit(0)

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
OUTPUT = os.path.join(ASSETS, 'NFL-Stats.csv')

# ── Season year logic ────────────────────────────────────────────────────────
# NFL season starts in September. Jan–Jul we're in the off-season for that
# year's season, so point at the completed prior season.
_today = date.today()
SEASON_YEAR = _today.year if _today.month >= 8 else _today.year - 1
PRIOR_YEAR  = SEASON_YEAR - 1

# Blend current stats toward prior over the first N weeks of the season.
# At 0 weeks played → 100% prior; at BLEND_FULL_WEEKS → 100% current.
BLEND_FULL_WEEKS = 8

# ── League averages used when a stat can't be computed ──────────────────────
LG = {
    'RushYdsAtt':    4.44,
    'PassYdsAtt':    7.175,
    'oRushPerGame':  26.95,
    'oPassPerGame':  32.69,
    'oYdsPerPoint':  15.053,
    'oPtsPerPlay':   0.3715,
    'oPlaysGame':    62.084,
}

# ── nfl_data_py abbreviation → display name (matches NFL-Teams.csv) ──────────
TEAM_NAMES = {
    'ARI': 'Arizona Cardinals',    'ATL': 'Atlanta Falcons',
    'BAL': 'Baltimore Ravens',     'BUF': 'Buffalo Bills',
    'CAR': 'Carolina Panthers',    'CHI': 'Chicago Bears',
    'CIN': 'Cincinnati Bengals',   'CLE': 'Cleveland Browns',
    'DAL': 'Dallas Cowboys',       'DEN': 'Denver Broncos',
    'DET': 'Detroit Lions',        'GB':  'Green Bay Packers',
    'HOU': 'Houston Texans',       'IND': 'Indianapolis Colts',
    'JAX': 'Jacksonville Jaguars', 'KC':  'Kansas City Chiefs',
    'LV':  'Las Vegas Raiders',    'LAC': 'Los Angeles Chargers',
    'LA':  'Los Angeles Rams',     'MIA': 'Miami Dolphins',
    'MIN': 'Minnesota Vikings',    'NE':  'New England Patriots',
    'NO':  'New Orleans Saints',   'NYG': 'New York Giants',
    'NYJ': 'New York Jets',        'PHI': 'Philadelphia Eagles',
    'PIT': 'Pittsburgh Steelers',  'SF':  'San Francisco 49ers',
    'SEA': 'Seattle Seahawks',     'TB':  'Tampa Bay Buccaneers',
    'TEN': 'Tennessee Titans',     'WAS': 'Washington Commanders',
}


def _safe(val, fallback: float) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) and v > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def fetch_pbp(year: int):
    """Aggregate PBP into (off_df, def_df, games_per_team) or None."""
    print(f'[NFL] Fetching {year} play-by-play...')
    cols = [
        'posteam', 'defteam', 'game_id', 'season_type',
        'rush_attempt', 'rushing_yards',
        'pass_attempt', 'passing_yards', 'sack',
        'yards_gained',
    ]
    try:
        pbp = nfl.import_pbp_data([year], columns=cols)
    except Exception as exc:
        print(f'[NFL] PBP fetch failed for {year}: {exc}')
        return None

    pbp = pbp[
        (pbp['season_type'] == 'REG') &
        pbp['posteam'].notna() &
        (pbp['posteam'] != '')
    ].copy()

    if pbp.empty:
        print(f'[NFL] No regular-season PBP rows for {year}.')
        return None

    # Convert numeric columns safely
    for c in ['rush_attempt', 'rushing_yards', 'pass_attempt',
              'passing_yards', 'sack', 'yards_gained']:
        pbp[c] = pd.to_numeric(pbp[c], errors='coerce').fillna(0)

    games_o = pbp.groupby('posteam')['game_id'].nunique().rename('gp')
    games_d = pbp.groupby('defteam')['game_id'].nunique().rename('gp')

    off = pbp.groupby('posteam').agg(
        rush_att  = ('rush_attempt',  'sum'),
        rush_yds  = ('rushing_yards', 'sum'),
        pass_att  = ('pass_attempt',  'sum'),
        pass_yds  = ('passing_yards', 'sum'),
        sacks     = ('sack',          'sum'),
        total_yds = ('yards_gained',  'sum'),
    ).join(games_o)

    def_ = pbp.groupby('defteam').agg(
        d_rush_att  = ('rush_attempt',  'sum'),
        d_rush_yds  = ('rushing_yards', 'sum'),
        d_pass_att  = ('pass_attempt',  'sum'),
        d_pass_yds  = ('passing_yards', 'sum'),
        d_sacks     = ('sack',          'sum'),
        d_total_yds = ('yards_gained',  'sum'),
    ).join(games_d)

    return off, def_, games_o


def fetch_scoring(year: int):
    """Return (pts_for_per_game, pts_against_per_game) Series by abbr."""
    print(f'[NFL] Fetching {year} schedule...')
    try:
        sched = nfl.import_schedules([year])
    except Exception as exc:
        print(f'[NFL] Schedule fetch failed for {year}: {exc}')
        return None, None

    sched = sched[
        (sched['game_type'] == 'REG') &
        sched['home_score'].notna() &
        sched['away_score'].notna()
    ]

    rows = []
    for _, row in sched.iterrows():
        rows.append({'team': row['home_team'], 'pf': row['home_score'], 'pa': row['away_score']})
        rows.append({'team': row['away_team'], 'pf': row['away_score'], 'pa': row['home_score']})

    df = pd.DataFrame(rows)
    return df.groupby('team')['pf'].mean(), df.groupby('team')['pa'].mean()


def fetch_home_adv(year: int) -> pd.Series:
    """Return home-field advantage in points per team."""
    try:
        sched = nfl.import_schedules([year])
    except Exception:
        return pd.Series(dtype=float)

    sched = sched[
        (sched['game_type'] == 'REG') &
        sched['home_score'].notna() &
        sched['away_score'].notna()
    ].copy()
    sched['diff'] = sched['home_score'] - sched['away_score']

    home_edge = sched.groupby('home_team')['diff'].mean()
    away_edge = sched.groupby('away_team')['diff'].mean() * -1
    adv = ((home_edge + away_edge) / 2).clip(lower=0.5, upper=5.5)
    return adv


def load_prior() -> pd.DataFrame | None:
    if not os.path.exists(OUTPUT):
        return None
    try:
        return pd.read_csv(OUTPUT, index_col='Team')
    except Exception:
        return None


def build():
    # Try current season first; fall back to prior year (off-season)
    pbp_result = fetch_pbp(SEASON_YEAR)
    using_prior_year = False
    if pbp_result is None:
        print(f'[NFL] No {SEASON_YEAR} data — trying {PRIOR_YEAR} (off-season).')
        pbp_result = fetch_pbp(PRIOR_YEAR)
        using_prior_year = True
        if pbp_result is None:
            print('[NFL] No data available for either year. Aborting.')
            sys.exit(1)

    off, def_, games_o = pbp_result
    score_year = PRIOR_YEAR if using_prior_year else SEASON_YEAR
    pf_pg, pa_pg = fetch_scoring(score_year)
    home_adv    = fetch_home_adv(score_year)
    prior       = load_prior()

    rows = []
    for abbr, team_name in sorted(TEAM_NAMES.items(), key=lambda x: x[1]):
        if abbr not in off.index:
            print(f'  [Skip] {team_name} not in PBP data.')
            continue

        o = off.loc[abbr]
        d = def_.loc[abbr] if abbr in def_.index else None
        gp = int(o.get('gp', 0))

        # Blend weight: 0 = all prior, 1 = all current
        # When using prior year for off-season, always use w=1 (full season complete)
        w = 1.0 if using_prior_year else min(gp / BLEND_FULL_WEEKS, 1.0)

        # ── Compute current-season stats ─────────────────────────────────────
        rush_att  = _safe(o.get('rush_att'),  LG['oRushPerGame'] * gp)
        pass_att  = _safe(o.get('pass_att'),  LG['oPassPerGame'] * gp)
        sacks     = _safe(o.get('sacks'),     0)
        rush_yds  = _safe(o.get('rush_yds'),  rush_att * LG['RushYdsAtt'])
        pass_yds  = _safe(o.get('pass_yds'),  pass_att * LG['PassYdsAtt'])
        total_yds = _safe(o.get('total_yds'), (rush_yds + pass_yds))
        gp_safe   = max(gp, 1)

        cur = {
            'RushYdsAtt':    rush_yds  / max(rush_att, 1),
            'PassYdsAtt':    pass_yds  / max(pass_att, 1),
            'oRushPerGame':  rush_att  / gp_safe,
            'oPassPerGame':  pass_att  / gp_safe,
            'oPlaysGame':    (rush_att + pass_att + sacks) / gp_safe,
            'oTotalYdsPG':   total_yds / gp_safe,
        }

        if d is not None:
            d_rush_att  = _safe(d.get('d_rush_att'),  LG['oRushPerGame'] * gp)
            d_pass_att  = _safe(d.get('d_pass_att'),  LG['oPassPerGame'] * gp)
            d_sacks     = _safe(d.get('d_sacks'),     0)
            d_rush_yds  = _safe(d.get('d_rush_yds'),  d_rush_att * LG['RushYdsAtt'])
            d_pass_yds  = _safe(d.get('d_pass_yds'),  d_pass_att * LG['PassYdsAtt'])
            d_total_yds = _safe(d.get('d_total_yds'), (d_rush_yds + d_pass_yds))
            d_gp        = max(int(d.get('gp', gp)), 1)
            cur.update({
                'dRushYdsAtt':   d_rush_yds  / max(d_rush_att, 1),
                'dPassYdsAtt':   d_pass_yds  / max(d_pass_att, 1),
                'dRushPerGame':  d_rush_att  / d_gp,
                'dPassPerGame':  d_pass_att  / d_gp,
                'dPlaysGame':    (d_rush_att + d_pass_att + d_sacks) / d_gp,
                'dTotalYdsPG':   d_total_yds / d_gp,
            })
        else:
            cur.update({k: LG.get(k, LG['RushYdsAtt']) for k in
                        ['dRushYdsAtt','dPassYdsAtt','dRushPerGame',
                         'dPassPerGame','dPlaysGame','dTotalYdsPG']})

        pf = _safe(pf_pg.get(abbr) if pf_pg is not None else None,
                   LG['oPtsPerPlay'] * LG['oPlaysGame'])
        pa = _safe(pa_pg.get(abbr) if pa_pg is not None else None,
                   LG['oPtsPerPlay'] * LG['oPlaysGame'])

        cur['oYdsPerPoint']   = cur['oTotalYdsPG'] / pf
        cur['dYardsPerPoint'] = cur['dTotalYdsPG'] / pa
        cur['oPtsPerPlay']    = pf / cur['oPlaysGame']
        cur['dPtsPerPlay']    = pa / cur['dPlaysGame']

        # ── Blend with prior CSV ─────────────────────────────────────────────
        def b(col, cur_val, fallback=None):
            if prior is not None and team_name in prior.index:
                try:
                    p = float(prior.loc[team_name, col])
                    if math.isfinite(p):
                        return round(w * cur_val + (1 - w) * p, 3)
                except Exception:
                    pass
            return round(cur_val, 3)

        ha = float(home_adv.get(abbr, 2.5)) if abbr in home_adv.index else 2.5

        rows.append({
            'Team':           team_name,
            'RushYdsAtt':     b('RushYdsAtt',     cur['RushYdsAtt']),
            'dRushYdsAtt':    b('dRushYdsAtt',    cur['dRushYdsAtt']),
            'PassYdsAtt':     b('PassYdsAtt',     cur['PassYdsAtt']),
            'dPassYdsAtt':    b('dPassYdsAtt',    cur['dPassYdsAtt']),
            'oRushPerGame':   b('oRushPerGame',   cur['oRushPerGame']),
            'dRushPerGame':   b('dRushPerGame',   cur['dRushPerGame']),
            'oPassPerGame':   b('oPassPerGame',   cur['oPassPerGame']),
            'dPassPerGame':   b('dPassPerGame',   cur['dPassPerGame']),
            'oYdsPerPoint':   b('oYdsPerPoint',   cur['oYdsPerPoint']),
            'dYardsPerPoint': b('dYardsPerPoint', cur['dYardsPerPoint']),
            'oPtsPerPlay':    b('oPtsPerPlay',    cur['oPtsPerPlay']),
            'dPtsPerPlay':    b('dPtsPerPlay',    cur['dPtsPerPlay']),
            'oPlays/Game':    b('oPlaysGame',     cur['oPlaysGame']),
            'dPlaysGame':     b('dPlaysGame',     cur['dPlaysGame']),
            'HomeAdv':        round(ha, 2),
        })
        print(f'  {team_name}: {gp} games, blend {w:.0%} current')

    if not rows:
        print('[NFL] No rows generated. Aborting.')
        sys.exit(1)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT, index=False)
    print(f'[NFL] Wrote {len(rows)} teams → {OUTPUT}')


if __name__ == '__main__':
    build()
