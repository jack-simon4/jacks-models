"""
Fetch today's MLB moneylines from The Odds API and write MLB-Odds.json.

Output: src/assets/MLB-Odds.json
  {
    "Los Angeles Dodgers": {"home_ml": "-180", "away_ml": "+155", "home_team": "Los Angeles Dodgers", "away_team": "San Francisco Giants"},
    ...
  }
Keyed by home team name so generate_top_picks.py can look up odds by game.

Requires env var: ODDS_API_KEY
Free tier: 500 requests/month.  This script makes 1 request per run.
"""

import json
import os
import sys

import requests

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
OUTPUT = os.path.join(ASSETS, 'MLB-Odds.json')

API_URL = 'https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/'

# Bookmaker preference order — first available is used
PREFERRED_BOOKS = ['fanduel', 'draftkings', 'betmgm', 'caesars', 'pointsbet']


def american_from_decimal(dec: float) -> str:
    if dec >= 2.0:
        val = int(round((dec - 1) * 100))
        return f'+{val}'
    else:
        val = int(round(-100 / (dec - 1)))
        return str(-val)


def fetch_mlb_odds():
    api_key = os.environ.get('ODDS_API_KEY', '')
    if not api_key:
        print('[Odds] ODDS_API_KEY not set — writing empty odds file.')
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return

    params = {
        'apiKey': api_key,
        'regions': 'us',
        'markets': 'h2h',
        'oddsFormat': 'american',
        'bookmakers': ','.join(PREFERRED_BOOKS),
    }

    try:
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f'[Odds] API request failed: {exc}')
        sys.exit(1)

    remaining = resp.headers.get('x-requests-remaining', '?')
    print(f'[Odds] Requests remaining this month: {remaining}')

    games = resp.json()
    print(f'[Odds] {len(games)} MLB games returned.')

    result = {}

    for game in games:
        home = game.get('home_team', '')
        away = game.get('away_team', '')
        bookmakers = game.get('bookmakers', [])

        # Pick the first preferred bookmaker that has h2h data
        home_ml = None
        away_ml = None
        book_used = None

        for preferred in PREFERRED_BOOKS:
            for bm in bookmakers:
                if bm['key'] != preferred:
                    continue
                for market in bm.get('markets', []):
                    if market['key'] != 'h2h':
                        continue
                    outcomes = {o['name']: o['price'] for o in market.get('outcomes', [])}
                    if home in outcomes and away in outcomes:
                        home_price = outcomes[home]
                        away_price = outcomes[away]
                        # american format: negative number for favorites
                        home_ml = str(int(home_price)) if home_price < 0 else f'+{int(home_price)}'
                        away_ml = str(int(away_price)) if away_price < 0 else f'+{int(away_price)}'
                        book_used = preferred
                        break
                if home_ml is not None:
                    break
            if home_ml is not None:
                break

        if home_ml is None:
            print(f'  [Skip] {away} @ {home} — no usable h2h line found.')
            continue

        result[home] = {
            'home_team': home,
            'away_team': away,
            'home_ml': home_ml,
            'away_ml': away_ml,
            'book': book_used,
        }
        print(f'  {away} @ {home}: {away} {away_ml} / {home} {home_ml} ({book_used})')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(f'[Odds] Saved {len(result)} games -> {OUTPUT}')


if __name__ == '__main__':
    fetch_mlb_odds()
