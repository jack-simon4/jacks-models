"""
Fetch today's MLB starting lineups from the official MLB Stats API
and write MLB-Lineups.csv.

Format: Team (e.g. "Arizona Diamondbacks1") → Player name

Lineups are typically posted 1-3 hours before first pitch.
Run this script around 1 PM ET for best coverage of afternoon/evening games.
"""

import os
from datetime import date

import pandas as pd
import statsapi

OUTPUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Lineups.csv')
)


def fetch_mlb_lineups():
    today = date.today().strftime('%m/%d/%Y')
    print(f'[Lineups] Fetching lineups for {today}...')

    schedule = statsapi.schedule(date=today, sportId=1)
    if not schedule:
        print('[Lineups] No games scheduled today.')
        return

    rows = []
    for game in schedule:
        game_id = game['game_id']
        away_name = game.get('away_name', '')
        home_name = game.get('home_name', '')

        try:
            data = statsapi.get('game', {
                'gamePk': game_id,
                'hydrate': 'lineups',
            })
        except Exception as exc:
            print(f'[Lineups] Could not fetch game {game_id}: {exc}')
            continue

        box = data.get('liveData', {}).get('boxscore', {}).get('teams', {})

        for side, team_name in (('away', away_name), ('home', home_name)):
            team_data = box.get(side, {})
            batting_order = team_data.get('battingOrder', [])
            players = team_data.get('players', {})

            if not batting_order:
                print(f'[Lineups]   No lineup yet for {team_name}')
                continue

            for slot, pid in enumerate(batting_order[:9], start=1):
                player_key = f'ID{pid}'
                full_name = (
                    players.get(player_key, {})
                           .get('person', {})
                           .get('fullName', '')
                )
                if full_name:
                    rows.append({'Team': f'{team_name}{slot}', 'Player': full_name})

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(OUTPUT, index=False)
        print(f'[Lineups] Saved {len(rows)} entries ({len(rows) // 9} lineups) → {OUTPUT}')
    else:
        print('[Lineups] No lineup data available yet for today.')


if __name__ == '__main__':
    fetch_mlb_lineups()
