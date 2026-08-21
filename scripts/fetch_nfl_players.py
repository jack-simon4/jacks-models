"""
Fetch NFL starting QB and key RB individual stats for the scoreboard model.

Outputs:
  NFL-QBs.csv  — one projected starting QB per team
    Team, Name, PassYdsAtt, PassAttGame, CompPct, TDRate, INTRate

  NFL-RBs.csv  — top 3 non-QB rushers per team
    Team, Name, RushYdsCarry, RushAttGame

Starting QB determination:
  1. QB with the most pass attempts this season = de-facto starter.
  2. If that player appears on the most recent injury report as Out or
     Doubtful, promote the next QB by attempt count.
  3. Off-season / no current-season data -> use prior completed season.

Early-season blend: when fewer than BLEND_FULL_WEEKS games have been played,
stats are blended toward prior-season values (same logic as fetch_nfl_stats.py).

Rushers: uses nfl_data_py seasonal data + roster positions to exclude QBs,
so mobile-QB rushing yards don't inflate the RB component.
"""

import math
import os
import sys
from datetime import date

import pandas as pd

try:
    import nfl_data_py as nfl
except ImportError:
    print('[NFLPlayers] nfl-data-py not installed; skipping.')
    sys.exit(0)

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
QB_OUTPUT  = os.path.join(ASSETS, 'NFL-QBs.csv')
RB_OUTPUT  = os.path.join(ASSETS, 'NFL-RBs.csv')
REC_OUTPUT = os.path.join(ASSETS, 'NFL-Receivers.csv')

_today       = date.today()
SEASON_YEAR  = _today.year if _today.month >= 8 else _today.year - 1
PRIOR_YEAR   = SEASON_YEAR - 1
BLEND_FULL_WEEKS = 8

MIN_QB_ATTEMPTS  = 50   # minimum season attempts to qualify as a starter candidate
MIN_RB_CARRIES   = 15   # minimum season carries to appear in RB output
MIN_REC_TARGETS  = 20   # minimum season targets for a receiver to qualify
MAX_RBS_PER_TEAM = 3
MAX_REC_PER_TEAM = 4    # top WRs + TEs combined

LG_PASS_YPA = 7.175
LG_PASS_APG = 32.69
LG_RUSH_YPC = 4.44
LG_RUSH_APG = 6.5    # per-RB share (team total ~27 split among ~3-4 backs)

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


def fetch_seasonal(year: int) -> pd.DataFrame | None:
    """
    Aggregate weekly data into per-player season totals for the given year.
    Uses import_weekly_data (has team/position/name) instead of import_seasonal_data
    (which only has player_id).
    """
    print(f'[NFLPlayers] Fetching {year} seasonal data...')
    cols = [
        'player_id', 'player_display_name', 'position', 'recent_team', 'week',
        'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions',
        'carries', 'rushing_yards', 'rushing_tds',
        'targets', 'receptions', 'receiving_yards', 'receiving_tds',
    ]
    try:
        weekly = nfl.import_weekly_data([year], cols)
        if weekly is None or weekly.empty:
            print(f'[NFLPlayers] No weekly data for {year}.')
            return None
        # Regular season only
        weekly = weekly[weekly['week'].between(1, 18)].copy()
        if weekly.empty:
            return None
        # Aggregate to season totals, keeping last team/position seen
        agg = weekly.groupby('player_id').agg(
            player_display_name = ('player_display_name', 'last'),
            position            = ('position',             'last'),
            team                = ('recent_team',          'last'),
            games               = ('week',                 'count'),
            completions         = ('completions',          'sum'),
            attempts            = ('attempts',             'sum'),
            passing_yards       = ('passing_yards',        'sum'),
            passing_tds         = ('passing_tds',          'sum'),
            interceptions       = ('interceptions',        'sum'),
            carries             = ('carries',              'sum'),
            rushing_yards       = ('rushing_yards',        'sum'),
            rushing_tds         = ('rushing_tds',          'sum'),
            targets             = ('targets',              'sum'),
            receiving_yards     = ('receiving_yards',      'sum'),
            receiving_tds       = ('receiving_tds',        'sum'),
        ).reset_index()
        print(f'[NFLPlayers] {year}: {len(agg)} player-seasons aggregated.')
        return agg
    except Exception as exc:
        print(f'[NFLPlayers] Seasonal fetch failed for {year}: {exc}')
        return None


def fetch_depth_chart(year: int) -> dict[str, list[str]]:
    """Return {team_abbr: [qb1_name, qb2_name, ...]} from most recent week."""
    try:
        dc = nfl.import_depth_charts([year])
        if dc is None or dc.empty:
            return {}
        qb_dc = dc[dc['position'] == 'QB'].copy()
        if qb_dc.empty:
            return {}
        max_week = qb_dc['week'].max()
        qb_dc = qb_dc[qb_dc['week'] == max_week].sort_values('depth_order')
        name_col = 'full_name' if 'full_name' in qb_dc.columns else 'player_name'
        team_col = 'club_code' if 'club_code' in qb_dc.columns else 'team'
        result = {}
        for team, grp in qb_dc.groupby(team_col):
            result[str(team)] = [str(n).strip() for n in grp[name_col] if n]
        print(f'[NFLPlayers] Depth chart loaded for {len(result)} teams (week {max_week}).')
        return result
    except Exception as exc:
        print(f'[NFLPlayers] Depth chart fetch failed: {exc}')
        return {}


def fetch_injured_out(year: int) -> set[tuple[str, str]]:
    """Return set of (team_abbr, player_name) for Out/Doubtful players."""
    try:
        inj = nfl.import_injuries([year])
        if inj is None or inj.empty:
            return set()
        max_week = inj['week'].max()
        inj = inj[
            (inj['week'] == max_week) &
            (inj['report_status'].isin(['Out', 'Doubtful', 'IR']))
        ]
        out_set = set()
        team_col = 'team' if 'team' in inj.columns else 'team_abbr'
        name_col = 'full_name' if 'full_name' in inj.columns else 'player_name'
        for _, row in inj.iterrows():
            t = str(row.get(team_col, '')).strip()
            n = str(row.get(name_col, '')).strip()
            if t and n:
                out_set.add((t, n))
        print(f'[NFLPlayers] Injury report: {len(out_set)} players Out/Doubtful (week {max_week}).')
        return out_set
    except Exception as exc:
        print(f'[NFLPlayers] Injury fetch failed: {exc}')
        return set()


def build_qb_csv(cur_df: pd.DataFrame | None, prior_df: pd.DataFrame | None,
                 games_played: int, depth_chart: dict, injured_out: set):
    """Write NFL-QBs.csv — one starting QB per team."""
    rows = []

    for abbr, team_name in sorted(TEAM_NAMES.items(), key=lambda x: x[1]):
        # Blend weight (0 = all prior, 1 = all current)
        w = min(games_played / BLEND_FULL_WEEKS, 1.0) if games_played > 0 else 0.0

        def get_qb_stats(df: pd.DataFrame | None, team_abbr: str, exclude_names: set = set()):
            """Find the primary QB for team_abbr in df, skipping names in exclude_names."""
            if df is None or df.empty:
                return None
            team_data = df[
                (df['team'] == team_abbr) &
                (df['position'] == 'QB') &
                (~df['player_display_name'].isin(exclude_names) if 'player_display_name' in df.columns
                 else ~df['player_name'].isin(exclude_names))
            ].copy()
            if team_data.empty:
                return None
            name_col = 'player_display_name' if 'player_display_name' in team_data.columns else 'player_name'
            team_data = team_data.sort_values('attempts', ascending=False)
            for _, row in team_data.iterrows():
                if _safe(row.get('attempts', 0), 0) >= MIN_QB_ATTEMPTS:
                    return row
            return None

        # Find current-season starter
        cur_row = get_qb_stats(cur_df, abbr)

        # Check if starter is injured — if so, promote backup
        if cur_row is not None:
            name_col = 'player_display_name' if cur_df is not None and 'player_display_name' in cur_df.columns else 'player_name'
            starter_name = str(cur_row.get(name_col, '')).strip()
            if (abbr, starter_name) in injured_out:
                print(f'  [{team_name}] {starter_name} is Out/Doubtful — promoting backup.')
                cur_row = get_qb_stats(cur_df, abbr, exclude_names={starter_name})

        # Fall back to prior season if no current data
        prior_row = get_qb_stats(prior_df, abbr)
        if cur_row is None and prior_row is None:
            print(f'  [{team_name}] No QB data found — using league averages.')
            rows.append({
                'Team': team_name, 'Name': 'Unknown',
                'PassYdsAtt': round(LG_PASS_YPA, 3),
                'PassAttGame': round(LG_PASS_APG, 3),
                'CompPct': 0.635, 'TDRate': 0.045, 'INTRate': 0.022,
            })
            continue

        def extract(row, att_col='attempts', yds_col='passing_yards',
                    cmp_col='completions', td_col='passing_tds', int_col='interceptions',
                    g_col='games'):
            if row is None:
                return None
            att  = _safe(row.get(att_col, 0),  1)
            yds  = _safe(row.get(yds_col, 0),  att * LG_PASS_YPA)
            cmp  = _safe(row.get(cmp_col, 0),  att * 0.635)
            tds  = _safe(row.get(td_col, 0),   att * 0.045)
            ints = max(float(row.get(int_col, 0) or 0), 0)
            gp   = max(_safe(row.get(g_col, 1), 1), 1)
            return {
                'ypa':     yds / att,
                'apg':     att / gp,
                'cmp_pct': cmp / att,
                'td_rate': tds / att,
                'int_rate': ints / att,
            }

        cur_stats   = extract(cur_row)
        prior_stats = extract(prior_row)

        # Blend current and prior
        def blend(key, cur_s, prior_s, fallback):
            c = cur_s[key]   if cur_s   else None
            p = prior_s[key] if prior_s else None
            if c is not None and p is not None:
                return w * c + (1 - w) * p
            return c if c is not None else (p if p is not None else fallback)

        use_row = cur_row if cur_row is not None else prior_row
        use_df  = prior_df if cur_row is None else cur_df
        use_df_cols = list(use_df.columns) if use_df is not None else []
        name_col = 'player_display_name' if 'player_display_name' in use_df_cols else 'player_name'
        starter_name = str(use_row.get(name_col, use_row.get('player_display_name', 'Unknown'))).strip()

        rows.append({
            'Team':       team_name,
            'Name':       starter_name,
            'PassYdsAtt': round(blend('ypa',     cur_stats, prior_stats, LG_PASS_YPA), 3),
            'PassAttGame': round(blend('apg',    cur_stats, prior_stats, LG_PASS_APG), 3),
            'CompPct':    round(blend('cmp_pct', cur_stats, prior_stats, 0.635), 3),
            'TDRate':     round(blend('td_rate', cur_stats, prior_stats, 0.045), 3),
            'INTRate':    round(blend('int_rate',cur_stats, prior_stats, 0.022), 4),
        })
        print(f'  [{team_name}] QB: {starter_name}  YPA={rows[-1]["PassYdsAtt"]}  APG={rows[-1]["PassAttGame"]}')

    pd.DataFrame(rows).to_csv(QB_OUTPUT, index=False)
    print(f'[NFLPlayers] Wrote {len(rows)} QBs -> {QB_OUTPUT}')


def build_rb_csv(cur_df: pd.DataFrame | None, prior_df: pd.DataFrame | None,
                 games_played: int):
    """Write NFL-RBs.csv — top non-QB rushers per team."""
    w = min(games_played / BLEND_FULL_WEEKS, 1.0) if games_played > 0 else 0.0
    rows = []

    # Non-QB positions that carry the ball
    RB_POSITIONS = {'RB', 'FB', 'WR', 'TE'}

    def get_team_rbs(df: pd.DataFrame | None, abbr: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        mask = (
            (df['team'] == abbr) &
            (df['position'].isin(RB_POSITIONS)) &
            (df['carries'] >= MIN_RB_CARRIES)
        )
        return df[mask].sort_values('carries', ascending=False).head(MAX_RBS_PER_TEAM)

    for abbr, team_name in sorted(TEAM_NAMES.items(), key=lambda x: x[1]):
        cur_rbs   = get_team_rbs(cur_df, abbr)
        prior_rbs = get_team_rbs(prior_df, abbr)

        # Use current if available, else prior, else skip
        use_rbs   = cur_rbs if not cur_rbs.empty else prior_rbs
        use_prior = cur_rbs.empty and not prior_rbs.empty

        if use_rbs.empty:
            print(f'  [{team_name}] No RB data — skipping.')
            continue

        name_col = 'player_display_name' if 'player_display_name' in use_rbs.columns else 'player_name'

        for _, rb in use_rbs.iterrows():
            name     = str(rb.get(name_col, 'Unknown')).strip()
            carries  = _safe(rb.get('carries', 0),        1)
            yds      = _safe(rb.get('rushing_yards', 0),  carries * LG_RUSH_YPC)
            gp       = max(_safe(rb.get('games', 1), 1), 1)
            cur_ypc  = yds / carries
            cur_apg  = carries / gp

            # Blend with prior if early season
            if not use_prior and not prior_rbs.empty:
                prior_match = prior_rbs[
                    prior_rbs[name_col].str.strip() == name
                ] if name_col in prior_rbs.columns else pd.DataFrame()
                if not prior_match.empty:
                    pr = prior_match.iloc[0]
                    pr_c = _safe(pr.get('carries', 0),       1)
                    pr_y = _safe(pr.get('rushing_yards', 0), pr_c * LG_RUSH_YPC)
                    pr_g = max(_safe(pr.get('games', 1), 1), 1)
                    cur_ypc = w * cur_ypc + (1 - w) * (pr_y / pr_c)
                    cur_apg = w * cur_apg + (1 - w) * (pr_c / pr_g)

            rows.append({
                'Team':         team_name,
                'Name':         name,
                'RushYdsCarry': round(cur_ypc, 3),
                'RushAttGame':  round(cur_apg, 2),
            })

        team_rbs = [r for r in rows if r['Team'] == team_name]
        names_str = ', '.join(f'{r["Name"]} ({r["RushYdsCarry"]} ypc)' for r in team_rbs)
        print(f'  [{team_name}] RBs: {names_str}')

    pd.DataFrame(rows).to_csv(RB_OUTPUT, index=False)
    print(f'[NFLPlayers] Wrote {len(rows)} RB rows -> {RB_OUTPUT}')


def build_receivers_csv(cur_df: pd.DataFrame | None, prior_df: pd.DataFrame | None,
                        games_played: int):
    """Write NFL-Receivers.csv — top WR/TE receivers per team."""
    w = min(games_played / BLEND_FULL_WEEKS, 1.0) if games_played > 0 else 0.0
    rows = []

    REC_POSITIONS = {'WR', 'TE'}

    def get_team_receivers(df: pd.DataFrame | None, abbr: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        mask = (
            (df['team'] == abbr) &
            (df['position'].isin(REC_POSITIONS)) &
            (df['targets'] >= MIN_REC_TARGETS)
        )
        return df[mask].sort_values('targets', ascending=False).head(MAX_REC_PER_TEAM)

    for abbr, team_name in sorted(TEAM_NAMES.items(), key=lambda x: x[1]):
        cur_recs   = get_team_receivers(cur_df, abbr)
        prior_recs = get_team_receivers(prior_df, abbr)
        use_recs   = cur_recs if not cur_recs.empty else prior_recs
        use_prior  = cur_recs.empty and not prior_recs.empty

        if use_recs.empty:
            print(f'  [{team_name}] No receiver data — skipping.')
            continue

        name_col = 'player_display_name' if 'player_display_name' in use_recs.columns else 'player_name'

        for _, rec in use_recs.iterrows():
            name    = str(rec.get(name_col, 'Unknown')).strip()
            pos     = str(rec.get('position', 'WR')).strip()
            tgts    = _safe(rec.get('targets', 0),          1)
            yds     = _safe(rec.get('receiving_yards', 0),  tgts * 8.0)
            tds     = max(float(rec.get('receiving_tds', 0) or 0), 0)
            gp      = max(_safe(rec.get('games', 1), 1), 1)
            cur_tpg = tgts / gp
            cur_ypt = yds  / tgts
            cur_tdg = tds  / gp

            # Blend with prior if early season and same player found
            if not use_prior and not prior_recs.empty and name_col in prior_recs.columns:
                prior_match = prior_recs[prior_recs[name_col].str.strip() == name]
                if not prior_match.empty:
                    pr     = prior_match.iloc[0]
                    pr_t   = _safe(pr.get('targets', 0),         1)
                    pr_y   = _safe(pr.get('receiving_yards', 0), pr_t * 8.0)
                    pr_td  = max(float(pr.get('receiving_tds', 0) or 0), 0)
                    pr_g   = max(_safe(pr.get('games', 1), 1), 1)
                    cur_tpg = w * cur_tpg + (1 - w) * (pr_t  / pr_g)
                    cur_ypt = w * cur_ypt + (1 - w) * (pr_y  / pr_t)
                    cur_tdg = w * cur_tdg + (1 - w) * (pr_td / pr_g)

            rows.append({
                'Team':        team_name,
                'Name':        name,
                'Position':    pos,
                'TargetsGame': round(cur_tpg, 2),
                'RecYdTarget': round(cur_ypt, 3),
                'TDGame':      round(cur_tdg, 3),
            })

        team_recs = [r for r in rows if r['Team'] == team_name]
        names_str = ', '.join(f'{r["Name"]} ({r["Position"]}, {r["TargetsGame"]} tgt/g)' for r in team_recs)
        print(f'  [{team_name}] Receivers: {names_str}')

    pd.DataFrame(rows).to_csv(REC_OUTPUT, index=False)
    print(f'[NFLPlayers] Wrote {len(rows)} receiver rows -> {REC_OUTPUT}')


def build():
    # Try current season; fall back to prior if no data yet
    cur_df = fetch_seasonal(SEASON_YEAR)

    games_played = 0
    if cur_df is not None and not cur_df.empty:
        games_col = 'games' if 'games' in cur_df.columns else None
        if games_col:
            games_played = int(cur_df[games_col].max() or 0)

    if cur_df is None or games_played == 0:
        print(f'[NFLPlayers] No {SEASON_YEAR} data — using {PRIOR_YEAR} only.')
        cur_df = None

    # Try prior years in order until we find data (library may not have latest season yet)
    prior_df = None
    for fallback_year in [PRIOR_YEAR, PRIOR_YEAR - 1, PRIOR_YEAR - 2]:
        prior_df = fetch_seasonal(fallback_year)
        if prior_df is not None and not prior_df.empty:
            print(f'[NFLPlayers] Using {fallback_year} as baseline season.')
            break

    # If we have no data at all, bail
    if cur_df is None and prior_df is None:
        print('[NFLPlayers] No data available for any recent season. Aborting.')
        sys.exit(1)

    depth_chart  = fetch_depth_chart(SEASON_YEAR)
    injured_out  = fetch_injured_out(SEASON_YEAR)

    build_qb_csv(cur_df, prior_df, games_played, depth_chart, injured_out)
    build_rb_csv(cur_df, prior_df, games_played)
    build_receivers_csv(cur_df, prior_df, games_played)


if __name__ == '__main__':
    build()
