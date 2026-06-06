"""
Fetch MLB pitcher stats (FanGraphs + Statcast) and write MLB-Pitchers.csv.

Columns: Name, k_percent, bb_percent, xba, xslg, xobp,
         single%, double%, triple%, home_run%, PA/G, Hand
"""

import os
import sys
import time

import pandas as pd
import pybaseball

OUTPUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Pitchers.csv')
)

# League-average proportions for hit types (used to estimate 2B/3B from H/HR allowed)
_SINGLE_FRAC  = 0.78
_DOUBLE_FRAC  = 0.19
_TRIPLE_FRAC  = 0.03


def _current_season():
    from datetime import datetime
    n = datetime.now()
    return n.year if n.month >= 3 else n.year - 1


def fetch_mlb_pitchers():
    year = _current_season()
    print(f'[Pitchers] Season: {year}')

    # ── FanGraphs: K%, BB%, Hand, G, TBF, H, HR ──────────────────────────
    print('[Pitchers] Fetching FanGraphs pitching stats...')
    try:
        fg = pybaseball.pitching_stats(year, year, qual=10)
    except Exception as exc:
        print(f'[Pitchers] FanGraphs failed: {exc}')
        sys.exit(1)

    wanted = ['Name', 'K%', 'BB%', 'Throws', 'G', 'TBF', 'H', 'HR']
    fg = fg[[c for c in wanted if c in fg.columns]].copy()
    fg.rename(columns={
        'K%':     'k_percent',
        'BB%':    'bb_percent',
        'Throws': 'Hand',
        'TBF':    'PA',
    }, inplace=True)

    # Compute hit-type rates from hits allowed (TBF as denominator)
    tbf = fg['PA'].replace(0, 1)
    non_hr = (fg['H'] - fg['HR']).clip(lower=0)
    fg['single%']   = (non_hr * _SINGLE_FRAC) / tbf
    fg['double%']   = (non_hr * _DOUBLE_FRAC) / tbf
    fg['triple%']   = (non_hr * _TRIPLE_FRAC) / tbf
    fg['home_run%'] = fg['HR'] / tbf
    fg['PA/G']      = fg['PA'] / fg['G']

    # ── Statcast: xBA, xSLG, xOBP ────────────────────────────────────────
    print('[Pitchers] Fetching Statcast pitcher expected stats...')
    sc = pd.DataFrame(columns=['Name', 'xba', 'xslg', 'xobp'])
    try:
        raw = pybaseball.statcast_pitcher_expected_stats(year)
        if not raw.empty and 'first_name' in raw.columns:
            raw['Name'] = raw['first_name'].str.strip() + ' ' + raw['last_name'].str.strip()
            sc = raw[['Name', 'xba', 'xslg', 'xobp']].copy()
    except Exception as exc:
        print(f'[Pitchers] Statcast fetch failed ({exc}); xBA/xSLG/xOBP will be 0.')

    time.sleep(1)

    # ── Merge ─────────────────────────────────────────────────────────────
    merged = fg.merge(sc, on='Name', how='left')
    merged[['xba', 'xslg', 'xobp']] = merged[['xba', 'xslg', 'xobp']].fillna(0)

    result = merged[[
        'Name', 'k_percent', 'bb_percent', 'xba', 'xslg', 'xobp',
        'single%', 'double%', 'triple%', 'home_run%', 'PA/G', 'Hand',
    ]].copy()

    result.to_csv(OUTPUT, index=False)
    print(f'[Pitchers] Saved {len(result)} rows → {OUTPUT}')


if __name__ == '__main__':
    fetch_mlb_pitchers()
