"""
Fetch NCAA Men's Basketball efficiency stats from Barttorvik (T-Rank) and
write NCAAM-Stats.csv.

Source: https://barttorvik.com/2027_team_results.csv  (free, no auth required)

Column mapping written to CSV:
  Team     = team name (normalised to match NCAAM-Teams.csv)
  AdjO     = adjoe  (Adjusted Offensive Efficiency per 100 poss)
  AdjD     = adjde  (Adjusted Defensive Efficiency per 100 poss)
  AdjT     = adjt   (Adjusted Tempo, possessions per 40 min)
  Orank    = adjoe / league_avg_adjoe
  Drank    = adjde / league_avg_adjde
  Trank    = adjt  / league_avg_adjt
  HomeAdv  = 3.5   (standard NCAA home-court advantage in points)
"""

import csv
import io
import os
import sys
import time
import requests
from datetime import datetime

ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
OUTPUT = os.path.join(ASSETS, 'NCAAM-Stats.csv')

# Season year (second year of the season, e.g. 2027 for 2026-27)
def season_year() -> int:
    now = datetime.now()
    return now.year + 1 if now.month >= 10 else now.year

HOME_ADV = 3.5

# Barttorvik name → our NCAAM-Teams.csv name
NAME_MAP = {
    'Cal St. Northridge':      'CSUN',
    'UMKC':                    'Kansas City',
    'McNeese St.':             'McNeese',
    'Nicholls St.':            'Nicholls',
    'SIU Edwardsville':        'SIUE',
    'Southeast Missouri St.':  'Southeast Missouri',
    'West Florida':            'Saint Francis',   # recent reclassification
    'St. Francis (BKN)':       'Saint Francis',
    'St. Francis (PA)':        'Saint Francis PA',
    "LIU":                     "Long Island University",
    'UTSA':                    'UT San Antonio',
    'UTRGV':                   'UT Rio Grande Valley',
    'UMass Lowell':            'Massachusetts-Lowell',
    'Col. of Charleston':      'College of Charleston',
    'N.C. A&T':                'NC A&T',
    'N.C. Central':            'NC Central',
    'UCSB':                    'UC Santa Barbara',
    'UCF':                     'Central Florida',
    'USF':                     'South Florida',
    'UIW':                     'Incarnate Word',
    'SIUE':                    'SIUE',
    'Loyola-Chicago':          'Loyola Chicago',
    'ETSU':                    'East Tennessee State',
    'SMU':                     'Southern Methodist',
    'BYU':                     'Brigham Young',
    'TCU':                     'Texas Christian',
    'LSU':                     'Louisiana State',
    'USC':                     'Southern California',
    'UNLV':                    'Nevada-Las Vegas',
    'UTEP':                    'Texas-El Paso',
    'UAB':                     'Alabama-Birmingham',
    'UConn':                   'Connecticut',
    'UMass':                   'Massachusetts',
    'UNC':                     'North Carolina',
    'UNI':                     'Northern Iowa',
    'UNCG':                    'UNC Greensboro',
    'UNCW':                    'UNC Wilmington',
    'UNC Asheville':           'UNC Asheville',
    'VCU':                     'Virginia Commonwealth',
}


def fetch_csv(year: int) -> list[dict]:
    url = f'https://barttorvik.com/{year}_team_results.csv'
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
            if r.status_code == 200 and r.text.strip().startswith('rank'):
                rows = list(csv.DictReader(io.StringIO(r.text)))
                print(f'[NCAAM Stats] Downloaded {len(rows)} teams from Barttorvik ({year})')
                return rows
            print(f'[NCAAM Stats] Unexpected response (attempt {attempt}): {r.text[:80]}')
        except Exception as exc:
            print(f'[NCAAM Stats] attempt {attempt}/3 failed: {exc}')
        if attempt < 3:
            time.sleep(5 * attempt)
    return []


def main():
    year = season_year()
    print(f'[NCAAM Stats] Season year: {year}')

    rows = fetch_csv(year)
    if not rows:
        print('[NCAAM Stats] No data — aborting.')
        sys.exit(1)

    # Parse numeric values
    parsed = []
    for row in rows:
        try:
            parsed.append({
                'team': row['team'].strip(),
                'adjO': float(row['adjoe']),
                'adjD': float(row['adjde']),
                'adjT': float(row['adjt']),
            })
        except (ValueError, KeyError):
            continue

    if not parsed:
        print('[NCAAM Stats] No parseable rows — aborting.')
        sys.exit(1)

    # League averages (for rank ratios)
    avg_o = sum(p['adjO'] for p in parsed) / len(parsed)
    avg_d = sum(p['adjD'] for p in parsed) / len(parsed)
    avg_t = sum(p['adjT'] for p in parsed) / len(parsed)
    print(f'[NCAAM Stats] League avg: AdjO={avg_o:.1f}  AdjD={avg_d:.1f}  AdjT={avg_t:.1f}')

    fieldnames = ['Team', 'AdjO', 'AdjD', 'AdjT', 'Orank', 'Drank', 'Trank', 'HomeAdv']
    csv_rows = []
    skipped = []

    for p in parsed:
        name = NAME_MAP.get(p['team'], p['team'])
        csv_rows.append({
            'Team':    name,
            'AdjO':    round(p['adjO'], 6),
            'AdjD':    round(p['adjD'], 6),
            'AdjT':    round(p['adjT'], 6),
            'Orank':   round(p['adjO'] / avg_o, 9),
            'Drank':   round(p['adjD'] / avg_d, 9),
            'Trank':   round(p['adjT'] / avg_t, 9),
            'HomeAdv': HOME_ADV,
        })

    csv_rows.sort(key=lambda r: r['Team'])

    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f'[NCAAM Stats] Wrote {len(csv_rows)} teams -> {OUTPUT}')


if __name__ == '__main__':
    main()
