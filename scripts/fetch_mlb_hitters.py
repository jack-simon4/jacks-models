"""
Fetch MLB hitter stats (FanGraphs + Statcast + platoon splits) and write MLB-Hitters.csv.

Columns: Name, k_percent, bb_percent, xba, xslg, xobp,
         single%, double%, triple%, home_run%, xOPS, wRops, wLops

wRops = OPS_vs_RHP / overall_xOPS  (fetched from FanGraphs splits; falls back to
wLops = OPS_vs_LHP / overall_xOPS   league-average platoon factors by batter hand)
"""

import os
import sys
import time

import pandas as pd
import pybaseball
import requests

OUTPUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Hitters.csv')
)

# Fallback platoon multipliers (RHP exposure ~70 %, LHP ~30 %)
# Format: batter_hand → (vs_RHP_factor, vs_LHP_factor)
_PLATOON = {
    'L': (1.04, 0.88),
    'R': (0.97, 1.07),
    'S': (1.01, 1.01),
}


def _current_season():
    from datetime import datetime
    n = datetime.now()
    return n.year if n.month >= 3 else n.year - 1


def _fg_splits(year: int, pitcher_hand: str) -> pd.DataFrame:
    """
    Query the FanGraphs splits API for batting stats filtered by pitcher handedness.
    Returns a DataFrame with at least Name and OPS columns (empty on failure).
    """
    url = 'https://www.fangraphs.com/api/leaders/splits/splits-leaders'
    params = {
        'strSplits': '',
        'splitquerytypes': '',
        'autoPt': 'true',
        'splitTeam': 'False',
        'statType': 'player',
        'statgroup': '2',
        'startDate': f'{year}-03-01',
        'endDate': f'{year}-11-01',
        'players': '',
        'groupBy': 'Name',
        'handedness': '',
        'pitcherHandedness': pitcher_hand,
        'season': str(year),
        'gameType': 'R',
        'customSplits': '',
        'lgFilter': '',
        'splitSeason': '1',
        'month': '0',
        'rost': '0',
        'age': '',
        'type': '0',
        'startInning': '0',
        'endInning': '9',
        'numteams': '0',
        'count': '0',
        'sort': '17,1',
        'pageitems': '2000',
        'pagenum': '1',
        'ind': '0',
        'qual': '50',
        'links': 'True',
    }
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    # FanGraphs may return the records under different keys
    for key in ('splitRecords', 'data', 'players'):
        if key in data and data[key]:
            return pd.DataFrame(data[key])
    return pd.DataFrame()


def _ops_column(df: pd.DataFrame):
    """Return the name of the OPS column if present, else None."""
    for c in ('OPS', 'ops', 'OBPplusSLG'):
        if c in df.columns:
            return c
    return None


def fetch_mlb_hitters():
    year = _current_season()
    print(f'[Hitters] Season: {year}')

    # ── FanGraphs: K%, BB%, hit types, handedness ─────────────────────────
    print('[Hitters] Fetching FanGraphs batting stats...')
    try:
        fg = pybaseball.batting_stats(year, year, qual=50)
    except Exception as exc:
        print(f'[Hitters] FanGraphs failed: {exc}')
        sys.exit(1)

    wanted = ['Name', 'K%', 'BB%', 'PA', 'G', 'H', '1B', '2B', '3B', 'HR', 'Bat']
    fg = fg[[c for c in wanted if c in fg.columns]].copy()
    fg.rename(columns={'K%': 'k_percent', 'BB%': 'bb_percent', 'Bat': 'Hand'}, inplace=True)

    # Derive singles if not present
    if '1B' not in fg.columns:
        fg['1B'] = (
            fg['H']
            - fg.get('2B', pd.Series(0, index=fg.index))
            - fg.get('3B', pd.Series(0, index=fg.index))
            - fg.get('HR', pd.Series(0, index=fg.index))
        ).clip(lower=0)

    pa = fg['PA'].replace(0, 1)
    fg['single%']   = fg['1B'] / pa
    fg['double%']   = fg.get('2B', pd.Series(0, index=fg.index)) / pa
    fg['triple%']   = fg.get('3B', pd.Series(0, index=fg.index)) / pa
    fg['home_run%'] = fg.get('HR', pd.Series(0, index=fg.index)) / pa

    # ── Statcast: xBA, xSLG, xOBP ────────────────────────────────────────
    print('[Hitters] Fetching Statcast batter expected stats...')
    sc = pd.DataFrame(columns=['Name', 'xba', 'xslg', 'xobp'])
    try:
        raw = pybaseball.statcast_batter_expected_stats(year, minPA=50)
        if not raw.empty and 'first_name' in raw.columns:
            raw['Name'] = raw['first_name'].str.strip() + ' ' + raw['last_name'].str.strip()
            sc = raw[['Name', 'xba', 'xslg', 'xobp']].copy()
    except Exception as exc:
        print(f'[Hitters] Statcast failed ({exc}); xBA/xSLG/xOBP will be 0.')

    time.sleep(1)

    merged = fg.merge(sc, on='Name', how='left')
    merged[['xba', 'xslg', 'xobp']] = merged[['xba', 'xslg', 'xobp']].fillna(0)
    merged['xOPS'] = merged['xobp'] + merged['xslg']

    # ── wRops / wLops from FanGraphs platoon splits ───────────────────────
    # Formula (from model): wRops = OPS_vs_RHP / xOPS, wLops = OPS_vs_LHP / xOPS
    print('[Hitters] Fetching FanGraphs platoon splits...')
    splits_ok = False
    try:
        time.sleep(1)
        sr = _fg_splits(year, 'R')
        time.sleep(1)
        sl = _fg_splits(year, 'L')

        rc = _ops_column(sr)
        lc = _ops_column(sl)

        if rc and lc and not sr.empty and not sl.empty:
            sr = sr[['Name', rc]].rename(columns={rc: 'OPS_vs_R'})
            sl = sl[['Name', lc]].rename(columns={lc: 'OPS_vs_L'})
            splits = sr.merge(sl, on='Name', how='outer')
            merged = merged.merge(splits, on='Name', how='left')
            xops = merged['xOPS'].replace(0, 1)
            merged['wRops'] = (merged['OPS_vs_R'].fillna(merged['xOPS'])) / xops
            merged['wLops'] = (merged['OPS_vs_L'].fillna(merged['xOPS'])) / xops
            merged.drop(columns=['OPS_vs_R', 'OPS_vs_L'], errors='ignore', inplace=True)
            splits_ok = True
            print('[Hitters] Platoon splits loaded from FanGraphs.')
    except Exception as exc:
        print(f'[Hitters] Splits unavailable ({exc}).')

    if not splits_ok:
        print('[Hitters] Falling back to handedness-based platoon approximation.')

        def _platoon(row):
            hand = row.get('Hand', 'R')
            if pd.isna(hand):
                hand = 'R'
            wr, wl = _PLATOON.get(str(hand).strip(), (1.00, 1.00))
            return pd.Series({'wRops': wr, 'wLops': wl})

        pt = merged.apply(_platoon, axis=1)
        merged['wRops'] = pt['wRops']
        merged['wLops'] = pt['wLops']

    # ── Save ──────────────────────────────────────────────────────────────
    keep = [
        'Name', 'k_percent', 'bb_percent', 'xba', 'xslg', 'xobp',
        'single%', 'double%', 'triple%', 'home_run%', 'xOPS', 'wRops', 'wLops',
    ]
    result = merged[[c for c in keep if c in merged.columns]].copy()
    result.to_csv(OUTPUT, index=False)
    print(f'[Hitters] Saved {len(result)} rows → {OUTPUT}')


if __name__ == '__main__':
    fetch_mlb_hitters()
