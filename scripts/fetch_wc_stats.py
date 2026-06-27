"""
Fetch 2026 FIFA World Cup results from football-data.org and update
national team stats in Soccer-Stats.csv.

Requires a free API key from https://www.football-data.org/client/register
stored as the FOOTBALL_DATA_API_KEY GitHub secret.

Blending: weight_actual = games_played / (games_played + PRIOR_GAMES)
  - PRIOR_GAMES = 7  →  pre-tournament stats treated as 7 games of data
  - After 3 group games:  3/10 = 30% actual
  - After 6 games (QF):   6/13 = 46% actual
  - After 7 games (final): 7/14 = 50% actual

wGF = GF / INTL_CONSTANT  (1.3 — international avg goals per game)
wGA = GA / INTL_CONSTANT
wLeague is structural strength — never updated from live results.
"""

import csv
import io
import os
import sys
import time

import requests

API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY', '')
BASE    = 'https://api.football-data.org/v4'

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
CSV_PATH = os.path.join(ASSETS, 'Soccer-Stats.csv')

# Treat prior stats as this many games when blending
PRIOR_GAMES = 7

# wGF = GF / INTL_CONSTANT, wGA = GA / INTL_CONSTANT
INTL_CONSTANT = 1.3

# Map football-data.org team names → our CSV names
FD_TO_CSV = {
    'Korea Republic':      'South Korea',
    'United States':        'United States',   # both match
    'Iran':                 'Iran',
    'Ivory Coast':          'Ivory Coast',
    "Côte d'Ivoire":        'Ivory Coast',
    'Czech Republic':       'Czechia',
    'Türkiye':              'Türkiye',
    'Turkey':               'Türkiye',
    'DR Congo':             'DR Congo',
    'Congo DR':             'DR Congo',
    'Democratic Republic of Congo': 'DR Congo',
    'Bosnia and Herzegovina': 'Bosnia & Herzegovina',
    'Bosnia & Herzegovina': 'Bosnia & Herzegovina',
    'New Zealand':          'New Zealand',
    'Curaçao':              'Curaçao',
    'Curacao':              'Curaçao',
    'Saudi Arabia':         'Saudi Arabia',
    'Cape Verde':           'Cape Verde',
    # Teams whose fd.org name already matches our CSV name need no entry
    # but listing them is harmless
    'Algeria': 'Algeria', 'Argentina': 'Argentina',
    'Australia': 'Australia', 'Austria': 'Austria',
    'Belgium': 'Belgium', 'Brazil': 'Brazil',
    'Canada': 'Canada', 'Colombia': 'Colombia',
    'Croatia': 'Croatia', 'Ecuador': 'Ecuador',
    'Egypt': 'Egypt', 'England': 'England',
    'France': 'France', 'Germany': 'Germany',
    'Ghana': 'Ghana', 'Haiti': 'Haiti',
    'Iraq': 'Iraq', 'Japan': 'Japan',
    'Jordan': 'Jordan', 'Mexico': 'Mexico',
    'Morocco': 'Morocco', 'Netherlands': 'Netherlands',
    'Norway': 'Norway', 'Panama': 'Panama',
    'Paraguay': 'Paraguay', 'Portugal': 'Portugal',
    'Qatar': 'Qatar', 'Scotland': 'Scotland',
    'Senegal': 'Senegal', 'South Africa': 'South Africa',
    'Spain': 'Spain', 'Sweden': 'Sweden',
    'Switzerland': 'Switzerland', 'Tunisia': 'Tunisia',
    'Uruguay': 'Uruguay', 'Uzbekistan': 'Uzbekistan',
}


def _get(endpoint: str, params: dict = None) -> dict:
    resp = requests.get(
        f'{BASE}{endpoint}',
        headers={'X-Auth-Token': API_KEY},
        params=params or {},
        timeout=30,
    )
    if resp.status_code == 429:
        time.sleep(61)
        resp = requests.get(
            f'{BASE}{endpoint}',
            headers={'X-Auth-Token': API_KEY},
            params=params or {},
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()


def fetch_results() -> dict[str, dict]:
    """
    Returns {csv_team_name: {'gf': total_goals_for, 'ga': total_goals_against,
                              'games': count}}
    for all finished WC 2026 matches.
    """
    print('[WC] Fetching finished matches from football-data.org...')
    data = _get('/competitions/WC/matches', {'season': 2026, 'status': 'FINISHED'})
    matches = data.get('matches', [])
    print(f'[WC] {len(matches)} finished matches found.')

    totals: dict[str, dict] = {}

    for m in matches:
        score = m.get('score', {}).get('fullTime', {})
        home_goals = score.get('home')
        away_goals = score.get('away')
        if home_goals is None or away_goals is None:
            continue

        home_fd = m['homeTeam'].get('name', '')
        away_fd = m['awayTeam'].get('name', '')

        home_csv = FD_TO_CSV.get(home_fd, home_fd)
        away_csv = FD_TO_CSV.get(away_fd, away_fd)

        for csv_name, gf, ga in [
            (home_csv, home_goals, away_goals),
            (away_csv, away_goals, home_goals),
        ]:
            if csv_name not in totals:
                totals[csv_name] = {'gf': 0, 'ga': 0, 'games': 0}
            totals[csv_name]['gf']    += gf
            totals[csv_name]['ga']    += ga
            totals[csv_name]['games'] += 1

    return totals


def update_csv(results: dict[str, dict]) -> bool:
    """Read Soccer-Stats.csv, blend WC results in, write back. Returns True if changed."""
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    # Identify which teams are WC national teams (have a HomeAdv of 0 or 0.05
    # AND are in our results dict). We only update teams found in WC results.
    changed = False
    updated_teams = []

    for row in rows:
        team = row['Team']
        if team not in results:
            continue

        r = results[team]
        games     = r['games']
        actual_gf = r['gf'] / games
        actual_ga = r['ga'] / games

        prior_gf  = float(row['GF'])
        prior_ga  = float(row['GA'])

        # Blend weight: how much to trust actual WC data
        w = games / (games + PRIOR_GAMES)

        new_gf = round(w * actual_gf + (1 - w) * prior_gf, 3)
        new_ga = round(w * actual_ga + (1 - w) * prior_ga, 3)
        new_wgf = round(new_gf / INTL_CONSTANT, 3)
        new_wga = round(new_ga / INTL_CONSTANT, 3)

        if (new_gf != prior_gf or new_ga != prior_ga):
            row['GF']  = new_gf
            row['GA']  = new_ga
            row['wGF'] = new_wgf
            row['wGA'] = new_wga
            changed = True
            updated_teams.append(
                f'  {team}: {games} games, w={w:.0%}  '
                f'GF {prior_gf:.3f}→{new_gf:.3f}  '
                f'GA {prior_ga:.3f}→{new_ga:.3f}'
            )

    if changed:
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f'[WC] Updated {len(updated_teams)} teams:')
        for line in updated_teams:
            print(line)
    else:
        print('[WC] No changes — stats already up to date.')

    return changed


def main():
    if not API_KEY:
        print('[WC] FOOTBALL_DATA_API_KEY not set — skipping.')
        sys.exit(0)

    results = fetch_results()
    if not results:
        print('[WC] No results returned. Nothing to update.')
        sys.exit(0)

    update_csv(results)


if __name__ == '__main__':
    main()
