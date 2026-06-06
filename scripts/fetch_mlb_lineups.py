"""
Fetch today's MLB starting lineups from the official MLB Stats API
and write MLB-Lineups.csv.

For teams that have not yet posted a lineup, the previous day's lineup
(from the existing CSV) is used as a fallback so the model always has
something to work with.

Format: "Team Name1" -> Player name (batting order slots 1-9)
"""

import os
from datetime import date

import pandas as pd
import statsapi

OUTPUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Lineups.csv')
)


def _load_existing():
    """Return existing lineup as {team_slot_key: player_name}, e.g. {'Arizona Diamondbacks1': 'Ketel Marte'}."""
    if not os.path.exists(OUTPUT):
        return {}
    try:
        df = pd.read_csv(OUTPUT)
        return dict(zip(df['Team'], df['Player']))
    except Exception:
        return {}


def fetch_mlb_lineups():
    today = date.today().strftime('%m/%d/%Y')
    print('[Lineups] Fetching lineups for', today)

    # Load previous lineup as fallback
    existing = _load_existing()
    print('[Lineups] Loaded', len(existing), 'existing lineup slots as fallback.')

    schedule = statsapi.schedule(date=today, sportId=1)
    if not schedule:
        print('[Lineups] No games scheduled today.')
        return

    # Build new lineup rows; track which teams we got live data for
    live_rows = []
    teams_with_live = set()

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
                print('[Lineups]   No lineup yet for', team_name, '-- will use fallback.')
                continue

            teams_with_live.add(team_name)
            for slot, pid in enumerate(batting_order[:9], start=1):
                full_name = (
                    players
                    .get('ID' + str(pid), {})
                    .get('person', {})
                    .get('fullName', '')
                )
                if full_name:
                    live_rows.append({'Team': team_name + str(slot), 'Player': full_name})

    # Merge: live rows take priority; fall back to existing for teams not yet announced
    all_teams_today = set()
    for game in schedule:
        all_teams_today.add(game.get('away_name', ''))
        all_teams_today.add(game.get('home_name', ''))

    fallback_rows = []
    fallback_count = 0
    for team_name in sorted(all_teams_today - teams_with_live):
        team_slots = [existing.get(team_name + str(slot), '') for slot in range(1, 10)]
        if any(team_slots):
            for slot, player in enumerate(team_slots, start=1):
                if player:
                    fallback_rows.append({'Team': team_name + str(slot), 'Player': player})
            fallback_count += 1
            print('[Lineups]   Using previous lineup for', team_name)
        else:
            print('[Lineups]   No data at all for', team_name)

    all_rows = live_rows + fallback_rows
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUTPUT, index=False)
        live_teams = len(teams_with_live)
        total_teams = len(all_teams_today)
        print('[Lineups] Saved', len(all_rows), 'entries:',
              live_teams, 'live lineups +', fallback_count, 'fallbacks (of', total_teams, 'teams)')
    else:
        print('[Lineups] No lineup data available.')


if __name__ == '__main__':
    fetch_mlb_lineups()
