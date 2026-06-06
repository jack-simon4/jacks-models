"""
Fetch today's MLB starting lineups from the official MLB Stats API
and write MLB-Lineups.csv.

Format: "Team Name1" -> Player name (batting order slot 1 through 9)

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
    print('[Lineups] Fetching lineups for', today)

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
            data = statsapi.get('game', {'gamePk': game_id, 'hydrate': 'lineups'})
        except Exception as exc:
            print('[Lineups] Could not fetch game', game_id, ':', exc)
            continue

        box = data.get('liveData', {}).get('boxscore', {}).get('teams', {})

        for side, team_name in (('away', away_name), ('home', home_name)):
            team_data = box.get(side, {})
            batting_order = team_data.get('battingOrder', [])
            players = team_data.get('players', {})

            if not batting_order:
                print('[Lineups]   No lineup yet for', team_name)
                continue

            for slot, pid in enumerate(batting_order[:9], start=1):
                full_name = (
                    players
                    .get('ID' + str(pid), {})
                    .get('person', {})
                    .get('fullName', '')
                )
                if full_name:
                    rows.append({'Team': team_name + str(slot), 'Player': full_name})

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(OUTPUT, index=False)
        print('[Lineups] Saved', len(rows), 'entries (' + str(len(rows) // 9) + ' lineups) ->', OUTPUT)
    else:
        print('[Lineups] No lineup data available yet for today.')


if __name__ == '__main__':
    fetch_mlb_lineups()
