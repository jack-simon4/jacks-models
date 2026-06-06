"""
Fetch MLB hitter stats (Baseball Reference + Statcast + platoon splits) and write MLB-Hitters.csv.

Blends current season and prior season using PA-weighted averaging to stabilise
small-sample stats early in the year.

Columns: Name, k_percent, bb_percent, xba, xslg, xobp,
         single%, double%, triple%, home_run%, xOPS, wRops, wLops
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


def _process_bref(df, min_pa):
    """Compute per-PA rates from a raw BRef batting DataFrame."""
    df = (
        df.sort_values('PA', ascending=False)
        .drop_duplicates('Name', keep='first')
        .query('PA >= @min_pa')
        .copy()
    )
    pa = df['PA'].replace(0, 1)
    df['1B']         = (df['H'] - df['2B'] - df['3B'] - df['HR']).clip(lower=0)
    df['k_percent']  = df['SO'] / pa * 100
    df['bb_percent'] = df['BB'] / pa * 100
    df['single%']    = df['1B'] / pa
    df['double%']    = df['2B'] / pa
    df['triple%']    = df['3B'] / pa
    df['home_run%']  = df['HR'] / pa
    df['xobp']       = df['OBP'].fillna(0.32) if 'OBP' in df.columns else 0.32
    df['_ascii']     = df['Name'].map(_ascii)
    keep = ['Name', '_ascii', 'PA', 'k_percent', 'bb_percent',
            'single%', 'double%', 'triple%', 'home_run%', 'xobp']
    return df[[c for c in keep if c in df.columns]].copy()


def _fetch_statcast(year, min_pa):
    """Fetch Statcast batter expected stats; returns DataFrame with _ascii, xba, xslg, sc_pa."""
    try:
        raw = pybaseball.statcast_batter_expected_stats(year, minPA=min_pa)
        if raw.empty:
            return pd.DataFrame()
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
        # Normalise the PA column name used by Statcast
        if 'pa' in raw.columns:
            raw = raw.rename(columns={'pa': 'sc_pa'})
        elif 'PA' in raw.columns:
            raw = raw.rename(columns={'PA': 'sc_pa'})
        else:
            raw['sc_pa'] = min_pa
        return raw[['_ascii', 'xba', 'xslg', 'sc_pa']].copy()
    except Exception as exc:
        print('[Hitters] Statcast', year, 'failed:', exc)
        return pd.DataFrame()


def _blend(cur, prev, rate_cols, pa_col='PA'):
    """PA-weight blend two DataFrames (both indexed on _ascii)."""
    m = cur.merge(prev, on='_ascii', how='outer', suffixes=('_c', '_p'))

    pc = m[f'{pa_col}_c'].fillna(0) if f'{pa_col}_c' in m.columns else pd.Series(0, index=m.index)
    pp = m[f'{pa_col}_p'].fillna(0) if f'{pa_col}_p' in m.columns else pd.Series(0, index=m.index)
    total = (pc + pp).clip(lower=1)

    out = pd.DataFrame(index=m.index)
    name_c = m['Name_c'] if 'Name_c' in m.columns else pd.Series(dtype=str)
    name_p = m['Name_p'] if 'Name_p' in m.columns else pd.Series(dtype=str)
    out['Name']    = name_c.combine_first(name_p)
    out['_ascii']  = m['_ascii']
    out[pa_col]    = total

    for col in rate_cols:
        vc = m[f'{col}_c'].fillna(0) if f'{col}_c' in m.columns else 0
        vp = m[f'{col}_p'].fillna(0) if f'{col}_p' in m.columns else 0
        out[col] = (vc * pc + vp * pp) / total

    return out


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
    r = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
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
    prior = year - 1
    print('[Hitters] Blending', prior, '+', year, 'seasons...')

    rate_cols = ['k_percent', 'bb_percent', 'single%', 'double%', 'triple%', 'home_run%', 'xobp']

    # --- Baseball Reference: current year ---
    print('[Hitters] Fetching BRef batting stats', year, '...')
    try:
        bref_cur = _process_bref(pybaseball.batting_stats_bref(year), MIN_PA)
    except Exception as exc:
        print('[Hitters] BRef', year, 'failed:', exc)
        sys.exit(1)

    time.sleep(1)

    # --- Baseball Reference: prior year ---
    print('[Hitters] Fetching BRef batting stats', prior, '...')
    try:
        bref_prev = _process_bref(pybaseball.batting_stats_bref(prior), MIN_PA)
    except Exception as exc:
        print('[Hitters] BRef', prior, 'failed (continuing without):', exc)
        bref_prev = pd.DataFrame(columns=bref_cur.columns)

    time.sleep(1)

    # --- PA-blend BRef rates ---
    blended = _blend(bref_cur, bref_prev, rate_cols, pa_col='PA')

    # --- Statcast: current year ---
    print('[Hitters] Fetching Statcast expected stats', year, '...')
    sc_cur = _fetch_statcast(year, MIN_PA)
    time.sleep(1)

    # --- Statcast: prior year (fallback for players not yet in current Statcast) ---
    print('[Hitters] Fetching Statcast expected stats', prior, '...')
    sc_prev = _fetch_statcast(prior, MIN_PA)
    time.sleep(1)

    # Blend Statcast by sc_pa
    sc_blended = pd.DataFrame()
    if not sc_cur.empty or not sc_prev.empty:
        if sc_cur.empty:
            sc_blended = sc_prev.rename(columns={'sc_pa': 'PA'})
            sc_blended['xba']  = sc_blended.get('xba', 0)
            sc_blended['xslg'] = sc_blended.get('xslg', 0)
        elif sc_prev.empty:
            sc_blended = sc_cur.rename(columns={'sc_pa': 'PA'})
        else:
            sc_blended = _blend(
                sc_cur.rename(columns={'sc_pa': 'PA'}),
                sc_prev.rename(columns={'sc_pa': 'PA'}),
                ['xba', 'xslg'],
                pa_col='PA',
            )

    # --- Merge blended BRef with blended Statcast ---
    merged = blended.copy()
    if not sc_blended.empty and {'_ascii', 'xba', 'xslg'}.issubset(sc_blended.columns):
        merged = merged.merge(sc_blended[['_ascii', 'xba', 'xslg']], on='_ascii', how='left')

    merged['xba']  = merged['xba'].fillna(0)  if 'xba'  in merged.columns else 0
    merged['xslg'] = merged['xslg'].fillna(0) if 'xslg' in merged.columns else 0
    merged['xOPS'] = merged['xobp'] + merged['xslg']
    merged.drop(columns=['_ascii', 'PA'], inplace=True)

    # --- Platoon splits ---
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

    keep = ['Name', 'k_percent', 'bb_percent', 'xba', 'xslg', 'xobp',
            'single%', 'double%', 'triple%', 'home_run%', 'xOPS', 'wRops', 'wLops']
    result = merged[[c for c in keep if c in merged.columns]].copy()
    result['Name'] = result['Name'].map(_fix_name)
    result.to_csv(OUTPUT, index=False, encoding='utf-8')
    print('[Hitters] Saved', len(result), 'rows ->', OUTPUT)


if __name__ == '__main__':
    fetch_mlb_hitters()
