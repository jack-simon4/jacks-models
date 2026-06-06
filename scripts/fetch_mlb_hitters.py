"""
Fetch MLB hitter stats (Baseball Reference + Statcast + platoon splits) and write MLB-Hitters.csv.

Columns: Name, k_percent, bb_percent, xba, xslg, xobp,
         single%, double%, triple%, home_run%, xOPS, wRops, wLops

Sources:
  Baseball Reference: K%, BB%, hit types, OBP (used as xobp proxy)
  Baseball Savant:    est_ba (xba), est_slg (xslg)
  FanGraphs splits:   wRops/wLops (OPS_vs_RHP/xOPS, OPS_vs_LHP/xOPS)
  MLB Stats API:      batter handedness fallback for platoon approximation
"""

import os
import sys
import time
import unicodedata

import pandas as pd
import pybaseball
import requests
import statsapi

OUTPUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Hitters.csv')
)

MIN_PA = 30
_PLATOON = {'L': (1.04, 0.88), 'R': (0.97, 1.07), 'S': (1.01, 1.01)}


def _current_season():
    from datetime import datetime
    n = datetime.now()
    return n.year if n.month >= 3 else n.year - 1


def _ascii(name):
    """Strip accents for fuzzy name matching."""
    return unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode('ascii')


def _fix_name(name):
    """Decode literal \\xNN escape sequences that pybaseball's bref parser emits.
    e.g. 'Julio Rodr\\xc3\\xadguez' -> 'Julio Rodriguez' (via UTF-8 decode)."""
    s = str(name)
    if '\\x' not in s:
        return s
    try:
        return s.encode('ascii').decode('unicode_escape').encode('latin-1').decode('utf-8')
    except Exception:
        return s


def _fg_splits(year, pitcher_hand):
    url = 'https://www.fangraphs.com/api/leaders/splits/splits-leaders'
    params = {
        'strSplits': '', 'splitquerytypes': '', 'autoPt': 'true',
        'splitTeam': 'False', 'statType': 'player', 'statgroup': '2',
        'startDate': str(year) + '-03-01', 'endDate': str(year) + '-11-01',
        'players': '', 'groupBy': 'Name', 'handedness': '',
        'pitcherHandedness': pitcher_hand, 'season': str(year),
        'gameType': 'R', 'customSplits': '', 'lgFilter': '',
        'splitSeason': '1', 'month': '0', 'rost': '0', 'age': '',
        'type': '0', 'startInning': '0', 'endInning': '9',
        'numteams': '0', 'count': '0', 'sort': '17,1',
        'pageitems': '2000', 'pagenum': '1', 'ind': '0', 'qual': '50',
        'links': 'True',
    }
    r = requests.get(url, params=params,
                     headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
    r.raise_for_status()
    data = r.json()
    for key in ('splitRecords', 'data', 'players'):
        if key in data and data[key]:
            return pd.DataFrame(data[key])
    return pd.DataFrame()


def _ops_col(df):
    for c in ('OPS', 'ops', 'OBPplusSLG'):
        if c in df.columns:
            return c
    return None


def _get_bat_hand(name, cache):
    if name in cache:
        return cache[name]
    try:
        results = statsapi.lookup_player(name, sportId=1)
        for p in results:
            code = p.get('batSide', {}).get('code', '')
            if code in ('R', 'L', 'S'):
                cache[name] = code
                return code
    except Exception:
        pass
    cache[name] = 'R'
    return 'R'


def fetch_mlb_hitters():
    year = _current_season()
    print('[Hitters] Season:', year)

    # Baseball Reference: K%, BB%, hit types, OBP
    print('[Hitters] Fetching Baseball Reference batting stats...')
    try:
        bref = pybaseball.batting_stats_bref(year)
    except Exception as exc:
        print('[Hitters] Baseball Reference failed:', exc)
        sys.exit(1)

    bref = (
        bref
        .sort_values('PA', ascending=False)
        .drop_duplicates(subset='Name', keep='first')
        .query('PA >= @MIN_PA')
        .copy()
    )

    pa = bref['PA'].replace(0, 1)
    bref['1B'] = (bref['H'] - bref['2B'] - bref['3B'] - bref['HR']).clip(lower=0)
    bref['k_percent']  = bref['SO'] / pa * 100
    bref['bb_percent'] = bref['BB'] / pa * 100
    bref['single%']    = bref['1B'] / pa
    bref['double%']    = bref['2B'] / pa
    bref['triple%']    = bref['3B'] / pa
    bref['home_run%']  = bref['HR'] / pa
    # Use actual OBP as xobp proxy (model normalizes against 0.320657 league avg)
    bref['xobp'] = bref['OBP'].fillna(0.32) if 'OBP' in bref.columns else 0.32
    bref['_ascii'] = bref['Name'].map(_ascii)

    time.sleep(1)

    # Statcast: est_ba (xba) and est_slg (xslg)
    print('[Hitters] Fetching Statcast batter expected stats...')
    sc = pd.DataFrame()
    try:
        raw = pybaseball.statcast_batter_expected_stats(year, minPA=MIN_PA)
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
        print('[Hitters] Statcast failed:', exc, '-- xba/xslg set to 0.')

    time.sleep(1)

    # Merge on ASCII-normalized name
    merged = bref[['Name', '_ascii', 'k_percent', 'bb_percent', 'xobp',
                   'single%', 'double%', 'triple%', 'home_run%']].copy()
    if not sc.empty:
        merged = merged.merge(sc, on='_ascii', how='left')
    if 'xba' not in merged.columns:
        merged['xba'] = 0
    if 'xslg' not in merged.columns:
        merged['xslg'] = 0
    merged['xba']  = merged['xba'].fillna(0)
    merged['xslg'] = merged['xslg'].fillna(0)
    merged['xOPS'] = merged['xobp'] + merged['xslg']
    merged.drop(columns=['_ascii'], inplace=True)

    # wRops / wLops from FanGraphs platoon splits
    print('[Hitters] Fetching FanGraphs platoon splits...')
    splits_ok = False
    try:
        time.sleep(1)
        sr = _fg_splits(year, 'R')
        time.sleep(1)
        sl = _fg_splits(year, 'L')
        rc = _ops_col(sr)
        lc = _ops_col(sl)
        if rc and lc and not sr.empty and not sl.empty:
            sr = sr[['Name', rc]].rename(columns={rc: 'OPS_R'})
            sl = sl[['Name', lc]].rename(columns={lc: 'OPS_L'})
            splits = sr.merge(sl, on='Name', how='outer')
            merged = merged.merge(splits, on='Name', how='left')
            xops = merged['xOPS'].replace(0, 1)
            merged['wRops'] = merged['OPS_R'].fillna(merged['xOPS']) / xops
            merged['wLops'] = merged['OPS_L'].fillna(merged['xOPS']) / xops
            merged.drop(columns=['OPS_R', 'OPS_L'], errors='ignore', inplace=True)
            splits_ok = True
            print('[Hitters] Platoon splits loaded from FanGraphs.')
    except Exception as exc:
        print('[Hitters] FanGraphs splits unavailable:', exc)

    if not splits_ok:
        print('[Hitters] Using handedness-based platoon approximation...')
        hand_cache = {}
        merged['_hand'] = [_get_bat_hand(n, hand_cache) for n in merged['Name']]
        merged['wRops'] = merged['_hand'].map(lambda h: _PLATOON.get(h, (1.0, 1.0))[0])
        merged['wLops'] = merged['_hand'].map(lambda h: _PLATOON.get(h, (1.0, 1.0))[1])
        merged.drop(columns=['_hand'], inplace=True)

    keep = [
        'Name', 'k_percent', 'bb_percent', 'xba', 'xslg', 'xobp',
        'single%', 'double%', 'triple%', 'home_run%', 'xOPS', 'wRops', 'wLops',
    ]
    result = merged[[c for c in keep if c in merged.columns]].copy()
    result['Name'] = result['Name'].map(_fix_name)
    result.to_csv(OUTPUT, index=False, encoding='utf-8')
    print('[Hitters] Saved', len(result), 'rows ->', OUTPUT)


if __name__ == '__main__':
    fetch_mlb_hitters()
