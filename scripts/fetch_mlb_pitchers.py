"""
Fetch MLB pitcher stats (Baseball Reference + Statcast) and write MLB-Pitchers.csv.

Blends current and prior season using BF-weighted averaging to stabilise
small-sample stats early in the year.

Columns: Name, k_percent, bb_percent, xba, xslg, xobp,
         single%, double%, triple%, home_run%, PA/G, Hand
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

MIN_BF = 30


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


def _load_existing_hands():
    if not os.path.exists(OUTPUT):
        return {}
    try:
        df = pd.read_csv(OUTPUT, usecols=['Name', 'Hand'], encoding='utf-8')
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


def _process_bref(df, min_bf):
    """Compute per-BF rates from a raw BRef pitching DataFrame."""
    if 'BF' not in df.columns and 'TBF' in df.columns:
        df = df.rename(columns={'TBF': 'BF'})
    df = (
        df.sort_values('BF', ascending=False)
        .drop_duplicates('Name', keep='first')
        .query('BF >= @min_bf')
        .copy()
    )
    bf = df['BF'].replace(0, 1)
    df['k_percent']  = df['SO'] / bf * 100
    df['bb_percent'] = df['BB'] / bf * 100
    df['_1B']        = (df['H'] - df['2B'] - df['3B'] - df['HR']).clip(lower=0)
    df['single%']    = df['_1B'] / bf
    df['double%']    = df['2B']  / bf
    df['triple%']    = df['3B']  / bf
    df['home_run%']  = df['HR']  / bf
    df['PA/G']       = df['BF']  / df['G']
    hbp = df['HBP'].fillna(0) if 'HBP' in df.columns else 0
    df['xobp']   = (df['H'] + df['BB'] + hbp) / bf
    df['_ascii'] = df['Name'].map(_ascii)
    keep = ['Name', '_ascii', 'BF', 'k_percent', 'bb_percent',
            'single%', 'double%', 'triple%', 'home_run%', 'xobp', 'PA/G']
    return df[[c for c in keep if c in df.columns]].copy()


def _fetch_statcast(year):
    """Fetch Statcast pitcher expected stats; returns DataFrame with _ascii, xba, xslg, sc_bf."""
    try:
        raw = pybaseball.statcast_pitcher_expected_stats(year)
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
        # Use pa column as weight for Statcast blending
        if 'pa' in raw.columns:
            raw = raw.rename(columns={'pa': 'sc_bf'})
        elif 'PA' in raw.columns:
            raw = raw.rename(columns={'PA': 'sc_bf'})
        else:
            raw['sc_bf'] = MIN_BF
        return raw[['_ascii', 'xba', 'xslg', 'sc_bf']].copy()
    except Exception as exc:
        print('[Pitchers] Statcast', year, 'failed:', exc)
        return pd.DataFrame()


def _blend(cur, prev, rate_cols, pa_col='BF'):
    """BF-weight blend two DataFrames merged on _ascii."""
    m = cur.merge(prev, on='_ascii', how='outer', suffixes=('_c', '_p'))

    pc = m[f'{pa_col}_c'].fillna(0) if f'{pa_col}_c' in m.columns else pd.Series(0, index=m.index)
    pp = m[f'{pa_col}_p'].fillna(0) if f'{pa_col}_p' in m.columns else pd.Series(0, index=m.index)
    total = (pc + pp).clip(lower=1)

    out = pd.DataFrame(index=m.index)
    name_c = m['Name_c'] if 'Name_c' in m.columns else pd.Series(dtype=str)
    name_p = m['Name_p'] if 'Name_p' in m.columns else pd.Series(dtype=str)
    out['Name']   = name_c.combine_first(name_p)
    out['_ascii'] = m['_ascii']
    out[pa_col]   = total

    for col in rate_cols:
        vc = m[f'{col}_c'].fillna(0) if f'{col}_c' in m.columns else 0
        vp = m[f'{col}_p'].fillna(0) if f'{col}_p' in m.columns else 0
        out[col] = (vc * pc + vp * pp) / total

    # PA/G: take current year's if available, else prior year
    if 'PA/G_c' in m.columns or 'PA/G_p' in m.columns:
        pag_c = m['PA/G_c'] if 'PA/G_c' in m.columns else pd.Series(dtype=float)
        pag_p = m['PA/G_p'] if 'PA/G_p' in m.columns else pd.Series(dtype=float)
        out['PA/G'] = pag_c.combine_first(pag_p)

    return out


def fetch_mlb_pitchers():
    year  = _current_season()
    prior = year - 1
    print('[Pitchers] Blending', prior, '+', year, 'seasons...')

    existing_hands = _load_existing_hands()
    rate_cols = ['k_percent', 'bb_percent', 'single%', 'double%', 'triple%', 'home_run%', 'xobp']

    # --- Baseball Reference: current year ---
    print('[Pitchers] Fetching BRef pitching stats', year, '...')
    try:
        bref_cur = _process_bref(pybaseball.pitching_stats_bref(year), MIN_BF)
    except Exception as exc:
        print('[Pitchers] BRef', year, 'failed:', exc)
        sys.exit(1)

    time.sleep(1)

    # --- Baseball Reference: prior year ---
    print('[Pitchers] Fetching BRef pitching stats', prior, '...')
    try:
        bref_prev = _process_bref(pybaseball.pitching_stats_bref(prior), MIN_BF)
    except Exception as exc:
        print('[Pitchers] BRef', prior, 'failed (continuing without):', exc)
        bref_prev = pd.DataFrame(columns=bref_cur.columns)

    time.sleep(1)

    # --- BF-blend BRef rates ---
    blended = _blend(bref_cur, bref_prev, rate_cols, pa_col='BF')

    # --- Statcast: current + prior year ---
    print('[Pitchers] Fetching Statcast pitcher expected stats', year, '...')
    sc_cur = _fetch_statcast(year)
    time.sleep(1)
    print('[Pitchers] Fetching Statcast pitcher expected stats', prior, '...')
    sc_prev = _fetch_statcast(prior)
    time.sleep(1)

    sc_blended = pd.DataFrame()
    if not sc_cur.empty or not sc_prev.empty:
        if sc_cur.empty:
            sc_blended = sc_prev.rename(columns={'sc_bf': 'BF'})
        elif sc_prev.empty:
            sc_blended = sc_cur.rename(columns={'sc_bf': 'BF'})
        else:
            sc_blended = _blend(
                sc_cur.rename(columns={'sc_bf': 'BF'}),
                sc_prev.rename(columns={'sc_bf': 'BF'}),
                ['xba', 'xslg'],
                pa_col='BF',
            )

    # --- Merge blended BRef with blended Statcast ---
    merged = blended.copy()
    if not sc_blended.empty and {'_ascii', 'xba', 'xslg'}.issubset(sc_blended.columns):
        merged = merged.merge(sc_blended[['_ascii', 'xba', 'xslg']], on='_ascii', how='left')

    merged['xba']  = merged['xba'].fillna(0)  if 'xba'  in merged.columns else 0
    merged['xslg'] = merged['xslg'].fillna(0) if 'xslg' in merged.columns else 0
    merged.drop(columns=['_ascii', 'BF'], inplace=True)

    # --- Pitcher handedness ---
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
