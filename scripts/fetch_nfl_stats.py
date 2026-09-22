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
from datetime import date, datetime, timedelta

import pandas as pd

try:
    import nfl_data_py as nfl
except ImportError:
    print('[NFL] nfl-data-py not installed; skipping.')
    sys.exit(0)

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
OUTPUT          = os.path.join(ASSETS, 'NFL-Stats.csv')
SPREADS_OUTPUT  = os.path.join(ASSETS, 'NFL-Spreads.csv')

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
    """Return (pts_for_per_game, pts_against_per_game, games_played) Series by abbr."""
    print(f'[NFL] Fetching {year} schedule...')
    empty = pd.Series(dtype=int)
    try:
        sched = nfl.import_schedules([year])
    except Exception as exc:
        print(f'[NFL] Schedule fetch failed for {year}: {exc}')
        return None, None, empty

    completed = sched[
        (sched['game_type'] == 'REG') &
        sched['home_score'].notna() &
        sched['away_score'].notna()
    ]

    if completed.empty:
        return None, None, empty

    rows = []
    for _, row in completed.iterrows():
        rows.append({'team': row['home_team'], 'pf': float(row['home_score']), 'pa': float(row['away_score'])})
        rows.append({'team': row['away_team'], 'pf': float(row['away_score']), 'pa': float(row['home_score'])})

    df       = pd.DataFrame(rows)
    games_gp = df.groupby('team').size()
    print(f'[NFL] {year} scoring: {len(games_gp)} teams, up to {int(games_gp.max())} games played.')
    return df.groupby('team')['pf'].mean(), df.groupby('team')['pa'].mean(), games_gp


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
    # ── Step 1: PBP for yardage stats ────────────────────────────────────────
    pbp_result = fetch_pbp(SEASON_YEAR)
    using_prior_year = False
    if pbp_result is None:
        print(f'[NFL] No {SEASON_YEAR} PBP — using {PRIOR_YEAR} yardage + {SEASON_YEAR} scoring.')
        pbp_result = fetch_pbp(PRIOR_YEAR)
        using_prior_year = True
        if pbp_result is None:
            print('[NFL] No data available for either year. Aborting.')
            sys.exit(1)

    off, def_, games_o_pbp = pbp_result

    # ── Step 2: Scoring — always try current season from schedule ─────────────
    # import_schedules([SEASON_YEAR]) works even when PBP isn't published yet.
    # This ensures projected scores update each week based on current-season PPG.
    pf_pg, pa_pg, games_o_sched = fetch_scoring(SEASON_YEAR)
    if pf_pg is None:
        # Current season has no completed games yet — fall back to prior season
        pf_pg, pa_pg, _ = fetch_scoring(PRIOR_YEAR)

    # ── Step 3: games_played for blend weight ────────────────────────────────
    # When PBP data comes from the prior year, derive games_played from the
    # current-season schedule so the blend weight reflects 2026 progress.
    if using_prior_year and games_o_sched is not None and not games_o_sched.empty:
        games_o = games_o_sched
    else:
        games_o = games_o_pbp

    home_adv = fetch_home_adv(SEASON_YEAR)
    if home_adv.empty:
        home_adv = fetch_home_adv(PRIOR_YEAR)
    prior    = load_prior()

    rows = []
    for abbr, team_name in sorted(TEAM_NAMES.items(), key=lambda x: x[1]):
        if abbr not in off.index:
            print(f'  [Skip] {team_name} not in PBP data.')
            continue

        o = off.loc[abbr]
        d = def_.loc[abbr] if abbr in def_.index else None

        # gp_pbp  = games played in the PBP dataset (used to compute per-game rates)
        # gp_cur  = games played in the current season (used for blend weight)
        gp_pbp = int(o.get('gp', 0))
        gp_raw = games_o.get(abbr) if isinstance(games_o, pd.Series) else None
        gp_cur = int(gp_raw) if gp_raw is not None and not pd.isna(gp_raw) else gp_pbp

        # Blend weight: 0 = 100% prior season, 1 = 100% current season
        w = min(gp_cur / BLEND_FULL_WEEKS, 1.0) if gp_cur > 0 else 0.0

        # ── Compute current-season stats ─────────────────────────────────────
        rush_att  = _safe(o.get('rush_att'),  LG['oRushPerGame'] * gp_pbp)
        pass_att  = _safe(o.get('pass_att'),  LG['oPassPerGame'] * gp_pbp)
        sacks     = _safe(o.get('sacks'),     0)
        rush_yds  = _safe(o.get('rush_yds'),  rush_att * LG['RushYdsAtt'])
        pass_yds  = _safe(o.get('pass_yds'),  pass_att * LG['PassYdsAtt'])
        total_yds = _safe(o.get('total_yds'), (rush_yds + pass_yds))
        gp_safe   = max(gp_pbp, 1)

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
            d_gp        = max(int(d.get('gp', gp_pbp)), 1)
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
        print(f'  {team_name}: {gp_cur} games (2026), blend {w:.0%} current')

    if not rows:
        print('[NFL] No rows generated. Aborting.')
        sys.exit(1)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT, index=False)
    print(f'[NFL] Wrote {len(rows)} teams → {OUTPUT}')


def update_spreads_csv(year: int):
    """Populate NFL-Spreads.csv with this week's upcoming matchups from nfl_data_py."""
    try:
        sched = nfl.import_schedules([year])
    except Exception as exc:
        print(f'[NFL] Schedule fetch for spreads failed: {exc}')
        return

    today_dt = date.today()
    reg = sched[
        (sched['game_type'] == 'REG') &
        sched['home_score'].isna()
    ].copy()

    if reg.empty:
        print('[NFL] No upcoming regular-season games found.')
        return

    reg['gameday_dt'] = pd.to_datetime(reg['gameday'], errors='coerce').dt.date
    reg = reg[reg['gameday_dt'].notna() & (reg['gameday_dt'] >= today_dt)]
    if reg.empty:
        print('[NFL] No upcoming games from today onward.')
        return

    target_week = int(reg['week'].min())
    this_week   = reg[reg['week'] == target_week]
    print(f'[NFL] Building spreads for Week {target_week}: {len(this_week)} games.')

    try:
        from zoneinfo import ZoneInfo
        ET  = ZoneInfo('America/New_York')
        UTC = ZoneInfo('UTC')
    except Exception:
        ET = UTC = None

    rows = []
    for _, game in this_week.iterrows():
        home_abbr = str(game['home_team'])
        away_abbr = str(game['away_team'])
        home_name = TEAM_NAMES.get(home_abbr, home_abbr)
        away_name = TEAM_NAMES.get(away_abbr, away_abbr)

        gameday  = str(game.get('gameday', ''))
        gametime = str(game.get('gametime', '') or '13:00')
        if not gametime or gametime == 'nan':
            gametime = '13:00'

        try:
            local_dt = datetime.strptime(f'{gameday} {gametime}', '%Y-%m-%d %H:%M')
            if ET and UTC:
                aware_dt      = local_dt.replace(tzinfo=ET)
                utc_dt        = aware_dt.astimezone(UTC)
            else:
                offset        = 4 if local_dt.month < 11 else 5
                utc_dt        = local_dt + timedelta(hours=offset)
            game_time_utc = utc_dt.strftime('%Y-%m-%dT%H:%M:00Z')
        except Exception:
            game_time_utc = f'{gameday}T17:00:00Z'

        try:
            spread_val = float(game.get('spread_line') or 0)
            if pd.isna(spread_val):
                spread_val = 0.0
        except (TypeError, ValueError):
            spread_val = 0.0

        rows.append({'Team': home_name, 'Spread':  spread_val, 'Opponent': away_name, 'GameTime': game_time_utc, 'IsHome': 'true'})
        rows.append({'Team': away_name, 'Spread': -spread_val, 'Opponent': home_name, 'GameTime': game_time_utc, 'IsHome': 'false'})

    if rows:
        df_out = pd.DataFrame(rows, columns=['Team', 'Spread', 'Opponent', 'GameTime', 'IsHome'])
        df_out.to_csv(SPREADS_OUTPUT, index=False)
        print(f'[NFL] NFL-Spreads.csv: {len(rows) // 2} games written (Week {target_week}).')


if __name__ == '__main__':
    build()
    update_spreads_csv(SEASON_YEAR)
