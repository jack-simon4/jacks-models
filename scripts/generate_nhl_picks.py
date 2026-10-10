"""
Generate NHL game picks and write nhl-picks.json.
Also saves predictions + actual scores to Firestore (Results page).

Uses NHL-Stats.csv and NHL-Goalies.csv (built by fetch_nhl_stats.py).
Fetches today's schedule from the NHL web API.

Output: src/assets/nhl-picks.json
"""

import csv
import json
import math
import os
import requests
from datetime import datetime, timedelta, timezone

ASSETS       = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_PATH   = os.path.join(ASSETS, 'NHL-Stats.csv')
GOALIES_PATH = os.path.join(ASSETS, 'NHL-Goalies.csv')
OUTPUT       = os.path.join(ASSETS, 'nhl-picks.json')

SA_JSON      = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
NHL_SCHEDULE = 'https://api-web.nhle.com/v1/schedule'

LG_SHOTS = 28.25  # league-average shots on goal per game (Angular model constant)

ABBREV_TO_NAME = {
    'ANA': 'Anaheim Ducks',
    'BOS': 'Boston Bruins',
    'BUF': 'Buffalo Sabres',
    'CGY': 'Calgary Flames',
    'CAR': 'Carolina Hurricanes',
    'CHI': 'Chicago Blackhawks',
    'COL': 'Colorado Avalanche',
    'CBJ': 'Columbus Blue Jackets',
    'DAL': 'Dallas Stars',
    'DET': 'Detroit Red Wings',
    'EDM': 'Edmonton Oilers',
    'FLA': 'Florida Panthers',
    'LAK': 'Los Angeles Kings',
    'MIN': 'Minnesota Wild',
    'MTL': 'Montréal Canadiens',
    'NSH': 'Nashville Predators',
    'NJD': 'New Jersey Devils',
    'NYI': 'New York Islanders',
    'NYR': 'New York Rangers',
    'OTT': 'Ottawa Senators',
    'PHI': 'Philadelphia Flyers',
    'PIT': 'Pittsburgh Penguins',
    'SJS': 'San Jose Sharks',
    'SEA': 'Seattle Kraken',
    'STL': 'St. Louis Blues',
    'TBL': 'Tampa Bay Lightning',
    'TOR': 'Toronto Maple Leafs',
    'UTA': 'Utah Mammoth',
    'VAN': 'Vancouver Canucks',
    'VGK': 'Vegas Golden Knights',
    'WSH': 'Washington Capitals',
    'WPG': 'Winnipeg Jets',
}

# League-average goalie used when no team goalie data is available
LG_AVG_GOALIE = {'name': 'TBD', 'gaa': 2.90, 'sv': 0.906}


def load_team_stats() -> dict:
    stats = {}
    if not os.path.exists(STATS_PATH):
        print('[NHL Picks] NHL-Stats.csv not found.')
        return stats
    with open(STATS_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                stats[row['Team'].strip()] = {
                    'ShotsF': float(row['ShotsF']),
                    'PP':     float(row['PP']),
                    'ShotsA': float(row['ShotsA']),
                    'S':      float(row['S%']),
                }
            except (ValueError, KeyError):
                pass
    print(f'[NHL Picks] Loaded stats for {len(stats)} teams.')
    return stats


def load_goalies() -> dict:
    """Returns {team_name: [goalie, ...]} sorted by GAA asc (best = lowest first)."""
    team_goalies: dict = {}
    if not os.path.exists(GOALIES_PATH):
        print('[NHL Picks] NHL-Goalies.csv not found.')
        return team_goalies
    with open(GOALIES_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = row.get('Player', '').strip()
            team = row.get('Team', '').strip()
            try:
                gaa = float(row['GAA'])
                sv  = float(row['Sv%'])
            except (ValueError, KeyError):
                continue
            if not name or not team:
                continue
            team_goalies.setdefault(team, []).append({'name': name, 'gaa': gaa, 'sv': sv})
    for team in team_goalies:
        team_goalies[team].sort(key=lambda g: g['gaa'])
    print(f'[NHL Picks] Loaded goalies for {len(team_goalies)} teams.')
    return team_goalies


def best_goalie(team_name: str, team_goalies: dict) -> dict:
    goalies = team_goalies.get(team_name, [])
    return goalies[0] if goalies else LG_AVG_GOALIE


def simulate(home_stats: dict, away_stats: dict,
             home_goalie: dict, away_goalie: dict) -> tuple[float, float]:
    """Python port of the Angular NHL simulation formula."""
    x_shots_home = home_stats['ShotsF'] * (away_stats['ShotsA'] / LG_SHOTS)
    x_shots_away = away_stats['ShotsF'] * (home_stats['ShotsA'] / LG_SHOTS)
    home_score = (
        -3.16
        + 0.01 * home_stats['PP']
        + 0.1  * x_shots_home
        + 0.31 * (home_stats['S'] + (1 - away_goalie['sv']) * 100) / 2
        + 0.03 * away_goalie['gaa']
    )
    away_score = (
        -3.16
        + 0.01 * away_stats['PP']
        + 0.1  * x_shots_away
        + 0.31 * (away_stats['S'] + (1 - home_goalie['sv']) * 100) / 2
        + 0.03 * home_goalie['gaa']
    )
    return round(home_score, 2), round(away_score, 2)


def win_prob(diff: float) -> float:
    return round(1 / (1 + math.exp(-0.7 * diff)), 3)


def confidence_label(edge: float) -> str:
    if edge >= 0.18: return 'Elite'
    if edge >= 0.10: return 'Strong'
    if edge >= 0.05: return 'Lean'
    return ''


def fetch_schedule(dates: list) -> list:
    games = []
    seen  = set()
    for date_str in dates:
        try:
            resp = requests.get(f'{NHL_SCHEDULE}/{date_str}', timeout=15)
            if resp.status_code != 200:
                print(f'[NHL Picks] Schedule {date_str}: HTTP {resp.status_code}')
                continue
            for day in resp.json().get('gameWeek', []):
                for g in day.get('games', []):
                    gid      = g.get('id')
                    gtype    = g.get('gameType', 0)
                    if gid not in seen and gtype == 2:  # regular season only
                        seen.add(gid)
                        games.append(g)
            print(f'[NHL Picks] Schedule {date_str}: {len([g for g in games if True])} total so far')
        except Exception as exc:
            print(f'[NHL Picks] Schedule {date_str} error: {exc}')
    print(f'[NHL Picks] {len(games)} unique regular-season games across {len(dates)} days.')
    return games


def save_to_firestore(games_data: list):
    if not SA_JSON:
        print('[NHL Picks] FIREBASE_SERVICE_ACCOUNT not set — skipping Firestore.')
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[NHL Picks] firebase-admin not installed — skipping Firestore.')
        return
    try:
        cred = credentials.Certificate(json.loads(SA_JSON))
        app  = firebase_admin.initialize_app(cred, name='nhl_picks')
        db   = fb_firestore.client(app)

        now_utc = datetime.now(timezone.utc)

        created = updated = skipped = 0
        for entry in games_data:
            doc_id  = f'nhl_{entry["gameId"]}'
            doc_ref = db.collection('games').document(doc_id)
            existing = doc_ref.get()

            actual_home = entry.get('actualHomeScore')
            actual_away = entry.get('actualAwayScore')

            # Determine if game is within 24 hours — lock predictions after that
            # so daily stat updates don't flip picks on game day.
            game_time_str = entry.get('gameTime', '')
            prediction_locked = False
            if game_time_str:
                try:
                    game_dt = datetime.fromisoformat(game_time_str.replace('Z', '+00:00'))
                    prediction_locked = (game_dt - now_utc).total_seconds() < 24 * 3600
                except ValueError:
                    pass

            if existing.exists:
                existing_data = existing.to_dict()
                if actual_home is not None and existing_data.get('actualHomeScore') is None:
                    doc_ref.update({
                        'actualHomeScore': actual_home,
                        'actualAwayScore': actual_away,
                    })
                    print(f'  [Updated] {entry["awayTeam"]} @ {entry["homeTeam"]}: {actual_away}-{actual_home}')
                    updated += 1
                elif existing_data.get('actualHomeScore') is None and not prediction_locked:
                    doc_ref.update({
                        'predictedHomeScore': entry['predictedHomeScore'],
                        'predictedAwayScore': entry['predictedAwayScore'],
                        'pick':               entry.get('pick', ''),
                        'winProb':            entry.get('winProb', 0),
                        'confidence':         entry.get('confidence', ''),
                    })
                    updated += 1
                else:
                    skipped += 1
            else:
                doc_ref.set({
                    'sport':              'NHL',
                    'gameId':             entry['gameId'],
                    'homeTeam':           entry['homeTeam'],
                    'awayTeam':           entry['awayTeam'],
                    'predictedHomeScore': entry['predictedHomeScore'],
                    'predictedAwayScore': entry['predictedAwayScore'],
                    'actualHomeScore':    actual_home,
                    'actualAwayScore':    actual_away,
                    'pick':               entry.get('pick', ''),
                    'winProb':            entry.get('winProb', 0),
                    'confidence':         entry.get('confidence', ''),
                    'gameTime':           entry.get('gameTime', ''),
                    'gameDate':           entry.get('gameTime', '')[:10],
                    'timestamp':          fb_firestore.SERVER_TIMESTAMP,
                })
                label = f'{actual_away}-{actual_home}' if actual_home is not None else 'upcoming'
                print(f'  [Saved] {entry["awayTeam"]} @ {entry["homeTeam"]} ({label})')
                created += 1

        firebase_admin.delete_app(app)
        print(f'[NHL Picks] Firestore: {created} created, {updated} updated, {skipped} skipped.')
    except Exception as exc:
        print(f'[NHL Picks] Firestore error: {exc}')


def main():
    stats        = load_team_stats()
    team_goalies = load_goalies()

    now   = datetime.now(timezone.utc)
    # Fetch today + next 2 days — NHL games often start at 23:00 UTC (7 PM ET),
    # so grabbing 3 days ensures we catch all of today's slate regardless of UTC rollover.
    dates = [(now + timedelta(days=d)).strftime('%Y-%m-%d') for d in range(3)]

    raw_games      = fetch_schedule(dates)
    picks          = []
    firestore_data = []
    skipped        = 0
    missing_teams  = set()

    for g in raw_games:
        game_id    = g.get('id')
        start      = g.get('startTimeUTC', '')
        home_info  = g.get('homeTeam') or {}
        away_info  = g.get('awayTeam') or {}
        home_abbrev = home_info.get('abbrev', '')
        away_abbrev = away_info.get('abbrev', '')

        home_name = ABBREV_TO_NAME.get(home_abbrev)
        away_name = ABBREV_TO_NAME.get(away_abbrev)
        if not home_name or not away_name:
            print(f'[NHL Picks] Unknown abbrev: {home_abbrev} / {away_abbrev}')
            skipped += 1
            continue

        h_stats = stats.get(home_name)
        a_stats = stats.get(away_name)
        if not h_stats or not a_stats:
            if not h_stats: missing_teams.add(home_name)
            if not a_stats: missing_teams.add(away_name)
            skipped += 1
            continue

        try:
            game_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            skipped += 1
            continue

        h_goalie = best_goalie(home_name, team_goalies)
        a_goalie = best_goalie(away_name, team_goalies)

        h_score, a_score = simulate(h_stats, a_stats, h_goalie, a_goalie)
        diff  = h_score - a_score
        wp    = win_prob(diff)

        if wp >= 0.5:
            pick_team, pick_wp = home_name, wp
        else:
            pick_team, pick_wp = away_name, round(1 - wp, 3)

        edge  = pick_wp - 0.5
        label = confidence_label(edge)

        game_state  = g.get('gameState', '')
        game_started = game_dt <= now
        h_pts = home_info.get('score')
        a_pts = away_info.get('score')
        actual_home = int(h_pts) if (h_pts is not None and game_state in ('FINAL', 'OFF')) else None
        actual_away = int(a_pts) if (a_pts is not None and game_state in ('FINAL', 'OFF')) else None

        entry = {
            'gameId':             game_id,
            'homeTeam':           home_name,
            'awayTeam':           away_name,
            'homeGoalie':         h_goalie['name'],
            'awayGoalie':         a_goalie['name'],
            'predictedHomeScore': h_score,
            'predictedAwayScore': a_score,
            'pick':               pick_team,
            'winProb':            round(pick_wp, 3),
            'confidence':         label,
            'gameTime':           start,
            'actualHomeScore':    actual_home,
            'actualAwayScore':    actual_away,
        }
        firestore_data.append(entry)

        # Only include upcoming games with a clear edge in the JSON picks file
        if not game_started and label:
            picks.append(entry)

    if missing_teams:
        print(f'[NHL Picks] Teams with no stats ({len(missing_teams)}): {sorted(missing_teams)}')

    upcoming = sum(1 for e in firestore_data if e['actualHomeScore'] is None)
    print(f'[NHL Picks] {len(firestore_data)} simulated: {upcoming} upcoming, '
          f'{len(firestore_data) - upcoming} completed. {skipped} skipped. {len(picks)} picks.')

    picks.sort(key=lambda p: p['winProb'], reverse=True)
    for i, p in enumerate(picks):
        p['rank'] = i + 1

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)
    print(f'[NHL Picks] {len(picks)} picks -> {OUTPUT}')

    save_to_firestore(firestore_data)


if __name__ == '__main__':
    main()
