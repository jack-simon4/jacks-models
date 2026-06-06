"""
Fetch MLB pitcher stats (Baseball Reference + Statcast) and write MLB-Pitchers.csv.

Columns: Name, k_percent, bb_percent, xba, xslg, xobp,
         single%, double%, triple%, home_run%, PA/G, Hand

Sources:
  Baseball Reference: K%, BB%, G, BF, H, 2B, 3B, HR, HBP (actual hit-type %)
  Baseball Savant:    est_ba (xba), est_slg (xslg); xobp derived from H+BB+HBP/BF
  Hand: preserved from existing CSV; new pitchers looked up via MLB Stats API.
"""

import os
import sys
import time
import unicodedata

import pandas as pd
import pybaseball
import statsapi

OUTPUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Pitchers.csv')
)

MIN_BF = 50


def _current_season():
    from datetime import datetime
    n = datetime.now()
    return n.year if n.month >= 3 else n.year - 1


def _ascii(name):
    """Strip accents for fuzzy name matching across data sources."""
    return unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode('ascii')


def _fix_name(name):
    """Decode literal \\xNN escape sequences that pybaseball's bref parser emits."""
    s = str(name)
    if '\\x' not in s:
        return s
    try:
        return s.encode('ascii').decode('unicode_escape').encode('latin-1').decode('utf-8')
    except Exception:
        return s


def _load_existing_hands():
    if not os.path.exists(OUTPUT):
        return {}
    try:
        df = pd.read_csv(OUTPUT, usecols=['Name', 'Hand'])
        return dict(zip(df['Name'], df['Hand']))
    except Exception:
        return {}


def _lookup_hand(name, cache):
    if name in cache:
        return cache[name]
    try:
        results = statsapi.lookup_player(name, sportId=1)
        for p in results:
            code = p.get('pitchHand', {}).get('code', '')
            if code in ('R', 'L'):
                cache[name] = code
                return code
    except Exception:
        pass
    cache[name] = 'R'
    return 'R'


def fetch_mlb_pitchers():
    year = _current_season()
    print('[Pitchers] Season:', year)

    existing_hands = _load_existing_hands()

    # Baseball Reference pitching stats
    print('[Pitchers] Fetching Baseball Reference pitching stats...')
    try:
        bref = pybaseball.pitching_stats_bref(year)
    except Exception as exc:
        print('[Pitchers] Baseball Reference failed:', exc)
        sys.exit(1)

    if 'BF' not in bref.columns and 'TBF' in bref.columns:
        bref = bref.rename(columns={'TBF': 'BF'})

    bref = (
        bref
        .sort_values('BF', ascending=False)
        .drop_duplicates(subset='Name', keep='first')
        .query('BF >= @MIN_BF')
        .copy()
    )

    bf = bref['BF'].replace(0, 1)
    bref['k_percent']  = bref['SO'] / bf * 100
    bref['bb_percent'] = bref['BB'] / bf * 100

    # Actual hit-type percentages from 2B, 3B, H, HR (BRef has these separately)
    bref['_1B'] = (bref['H'] - bref['2B'] - bref['3B'] - bref['HR']).clip(lower=0)
    bref['single%']   = bref['_1B']  / bf
    bref['double%']   = bref['2B']   / bf
    bref['triple%']   = bref['3B']   / bf
    bref['home_run%'] = bref['HR']   / bf
    bref['PA/G']      = bref['BF']   / bref['G']

    # xobp from actual OBP against (H + BB + HBP) / BF
    hbp = bref['HBP'].fillna(0) if 'HBP' in bref.columns else 0
    bref['xobp'] = (bref['H'] + bref['BB'] + hbp) / bf

    bref['_ascii'] = bref['Name'].map(_ascii)

    time.sleep(1)

    # Statcast: est_ba (xba) and est_slg (xslg)
    print('[Pitchers] Fetching Statcast pitcher expected stats...')
    sc = pd.DataFrame()
    try:
        raw = pybaseball.statcast_pitcher_expected_stats(year)
        if not raw.empty:
            name_col = 'last_name, first_name'
            if name_col in raw.columns:
                raw['Name'] = raw[name_col].apply(
                    lambda x: ' '.join(str(x).split(', ')[::-1]) if ', ' in str(x) else str(x)
                )
            elif 'first_name' in raw.columns:
                raw['Name'] = raw['first_name'].str.strip() + ' ' + raw['last_name'].str.strip()

            ba_col  = 'est_ba'  if 'est_ba'  in raw.columns else 'xba'
            slg_col = 'est_slg' if 'est_slg' in raw.columns else 'xslg'
            raw = raw.rename(columns={ba_col: 'xba', slg_col: 'xslg'})
            raw['_ascii'] = raw['Name'].map(_ascii)
            sc = raw[['_ascii', 'xba', 'xslg']].copy()
    except Exception as exc:
        print('[Pitchers] Statcast failed:', exc, '-- xba/xslg set to 0.')

    time.sleep(1)

    # Merge on ASCII-normalized name (handles accented characters)
    merged = bref[['Name', '_ascii', 'k_percent', 'bb_percent', 'xobp',
                   'single%', 'double%', 'triple%', 'home_run%', 'PA/G']].copy()
    if not sc.empty:
        merged = merged.merge(sc, on='_ascii', how='left')
    if 'xba' not in merged.columns:
        merged['xba'] = 0
    if 'xslg' not in merged.columns:
        merged['xslg'] = 0
    merged['xba']  = merged['xba'].fillna(0)
    merged['xslg'] = merged['xslg'].fillna(0)
    merged.drop(columns=['_ascii'], inplace=True)

    # Pitcher handedness
    print('[Pitchers] Resolving pitcher handedness...')
    hand_cache = dict(existing_hands)
    new_names = [n for n in merged['Name'] if n not in existing_hands]
    if new_names:
        print('[Pitchers]   Looking up', len(new_names), 'new pitcher(s) via MLB API...')
    merged['Hand'] = merged['Name'].apply(lambda n: _lookup_hand(n, hand_cache))

    result = merged[[
        'Name', 'k_percent', 'bb_percent', 'xba', 'xslg', 'xobp',
        'single%', 'double%', 'triple%', 'home_run%', 'PA/G', 'Hand',
    ]].copy()

    result['Name'] = result['Name'].map(_fix_name)
    result.to_csv(OUTPUT, index=False, encoding='utf-8')
    print('[Pitchers] Saved', len(result), 'rows ->', OUTPUT)


if __name__ == '__main__':
    fetch_mlb_pitchers()
