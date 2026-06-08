"""
Fetch today's MLB starting lineups from the official MLB Stats API
and write MLB-Lineups.csv.

Fallback strategy (in order):
  1. Live announced lineup from MLB Stats API
  2. Prior lineup from MLB-Last-Lineups.csv (persistent per-team history)

MLB-Last-Lineups.csv is never cleared — it stores the most recently seen
lineup for every team and is updated whenever live data arrives.
This ensures late-game teams (e.g. Dodgers with 7 PM starts) always appear
in the props table even before their lineup is officially posted.

Output format: Team column like "Arizona Diamondbacks1", Player column.
"""

import os
from datetime import date

import pandas as pd
import statsapi

OUTPUT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Lineups.csv')
)
HISTORY = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'MLB-Last-Lineups.csv')
)


def _load_history():
    """Load the persistent per-team lineup history: {team_slot_key: player_name}."""
    if not os.path.exists(HISTORY):
        return {}
    try:
        df = pd.read_csv(HISTORY, encoding='utf-8')
        return dict(zip(df['Team'], df['Player']))
    except Exception:
        return {}


def _save_history(history):
    """Persist the updated history dict back to CSV."""
    rows = [{'Team': k, 'Player': v} for k, v in sorted(history.items())]
    pd.DataFrame(rows).to_csv(HISTORY, index=False, encoding='utf-8')


def fetch_mlb_lineups():
    today = date.today().strftime('%m/%d/%Y')
    print('[Lineups] Fetching lineups for', today)

    # Load persistent history as the fallback source
    history = _load_history()
    print('[Lineups] History has', len(history), 'slots across all teams.')

    schedule = statsapi.schedule(date=today, sportId=1)
    if not schedule:
        print('[Lineups] No games scheduled today.')
        return

    # Fetch live lineups
    live_rows = []
    teams_with_live = set()

    for game in schedule:
        game_id   = game['game_id']
        away_name = game.get('away_name', '')
        home_name = game.get('home_name', '')

        try:
            data = statsapi.get('game', {'gamePk': game_id, 'hydrate': 'lineups'})
        except Exception as exc:
            print('[Lineups] Could not fetch game', game_id, ':', exc)
            continue

        box = data.get('liveData', {}).get('boxscore', {}).get('teams', {})
        # gameData.lineups is populated once teams officially submit pre-game lineups
        # (typically 2 h before first pitch) — available before liveData.boxscore is.
        gd_lineups = data.get('gameData', {}).get('lineups', {})

        for side, team_name in (('away', away_name), ('home', home_name)):
            team_data     = box.get(side, {})
            batting_order = team_data.get('battingOrder', [])
            players       = team_data.get('players', {})

            # If boxscore battingOrder isn't populated yet, try gameData.lineups
            if not batting_order:
                gd_key = 'homePlayers' if side == 'home' else 'awayPlayers'
                gd_players = gd_lineups.get(gd_key, [])
                if gd_players:
                    teams_with_live.add(team_name)
                    for slot, player in enumerate(gd_players[:9], start=1):
                        full_name = player.get('fullName', '')
                        if full_name:
                            live_rows.append({'Team': team_name + str(slot), 'Player': full_name})
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

    # Update history with every live slot we just received
    for row in live_rows:
        history[row['Team']] = row['Player']

    # Build today's lineup: live data + history fallback for unannounced teams
    all_teams_today = set()
    for game in schedule:
        all_teams_today.add(game.get('away_name', ''))
        all_teams_today.add(game.get('home_name', ''))
    all_teams_today.discard('')

    fallback_rows  = []
    fallback_count = 0

    for team_name in sorted(all_teams_today - teams_with_live):
        slots = [history.get(team_name + str(s), '') for s in range(1, 10)]
        if any(slots):
            for slot, player in enumerate(slots, start=1):
                if player:
                    fallback_rows.append({'Team': team_name + str(slot), 'Player': player})
            fallback_count += 1
            print('[Lineups]   Using last known lineup for', team_name)
        else:
            print('[Lineups]   No lineup data at all for', team_name)

    # Save updated history (includes today's live slots)
    _save_history(history)

    # Write today's complete lineup file
    all_rows = live_rows + fallback_rows
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUTPUT, index=False, encoding='utf-8')
        print('[Lineups] Saved', len(all_rows), 'entries:',
              len(teams_with_live), 'live +', fallback_count, 'from history',
              '(of', len(all_teams_today), 'teams today)')
    else:
        print('[Lineups] No lineup data available.')


if __name__ == '__main__':
    fetch_mlb_lineups()
