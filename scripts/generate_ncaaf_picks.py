"""
Generate NCAAF top picks for upcoming games and write ncaaf-picks.json.
Also saves predictions and actual scores to Firestore so they appear on
the Results page.

Uses NCAAF-Stats.csv (built by fetch_ncaaf_stats.py) for team ratings
and the CFBD API for the upcoming/completed game schedule.

Model is a direct Python port of the TypeScript NCAAF case in
ScoreboardComponent.runSimulation().

Output: src/assets/ncaaf-picks.json
"""

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone

import requests

API_KEY    = os.environ.get('CFBD_API_KEY', '')
SA_JSON    = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
BASE       = 'https://api.collegefootballdata.com'
ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_PATH = os.path.join(ASSETS, 'NCAAF-Stats.csv')
OUTPUT     = os.path.join(ASSETS, 'ncaaf-picks.json')

# Maps CFBD API team names → NCAAF-Stats.csv team names (inverse of fetch_ncaaf_stats.TEAM_NAME_MAP)
CFBD_TO_CSV: dict[str, str] = {
    'Appalachian State':    'App State',
    'Arizona State':        'Arizona St',
    'Arkansas State':       'Arkansas St',
    'Ball State':           'Ball St',
    'Boise State':          'Boise St',
    'Central Michigan':     'C Michigan',
    'Coastal Carolina':     'Coastal Car',
    'Colorado State':       'Colorado St',
    'East Carolina':        'E Carolina',
    'Eastern Michigan':     'E Michigan',
    'Florida International':'Florida Intl',
    'Florida State':        'Florida St',
    'Fresno State':         'Fresno St',
    'Georgia Southern':     'Georgia So',
    'Georgia State':        'Georgia St',
    'Hawaii':               "Hawai'i",
    'James Madison':        'J Madison',
    'Jacksonville State':   'Jacksonville St',
    'Kansas State':         'Kansas St',
    'Kent State':           'Kent St',
    'Miami (OH)':           'Miami OH',
    'Middle Tennessee':     'Middle Tenn',
    'Ole Miss':             'Mississippi',
    'Mississippi State':    'Mississippi St',
    'Northern Illinois':    'N Illinois',
    'North Texas':          'N Texas',
    'New Mexico State':     'New Mexico St',
    'Penn State':           'Penn St',
    'South Alabama':        'S Alabama',
    'South Florida':        'S Florida',
    'San Diego State':      'San Diego St',
    'San Jose State':       'San Jose St',
    'Texas State':          'Texas St',
    'Connecticut':          'UConn',
    'Louisiana Monroe':     'UL Monroe',
    'Massachusetts':        'UMass',
    'Utah State':           'Utah St',
    'Western Kentucky':     'W Kentucky',
    'Western Michigan':     'W Michigan',
    'Washington State':     'Washington St',
}


def load_stats() -> dict:
    """Parse NCAAF-Stats.csv by column position (has duplicate 'Last 3' headers)."""
    stats = {}
    if not os.path.exists(STATS_PATH):
        print('[NCAAF] NCAAF-Stats.csv not found.')
        return stats
    with open(STATS_PATH, encoding='utf-8') as f:
        lines = f.read().strip().split('\n')
    for line in lines[1:]:
        parts = line.split(',')
        if len(parts) < 19:
            continue
        try:
            team = parts[0].strip()
            stats[team] = {
                'oRating':    float(parts[2]),
                'dRating':    float(parts[3]),
                'wYdsPlay':   float(parts[6]),
                'wdYdsPlay':  float(parts[9]),
                'wYdsPt':     float(parts[12]),
                'wdYdsPt':    float(parts[15]),
                'PlaysGame':  float(parts[16]),
                'dPlaysGame': float(parts[17]),
                'HomeAdv':    float(parts[18]),
            }
        except (ValueError, IndexError):
            pass
    print(f'[NCAAF] Loaded stats for {len(stats)} teams.')
    return stats


def simulate(home: dict, away: dict) -> tuple[float, float]:
    """Port of the TypeScript NCAAF model formula."""
    home_adv = home['HomeAdv'] / 2
    home_score = (
        (0.5 * home['wYdsPlay'] * away['dRating'] + 0.5 * away['wdYdsPlay'] * home['oRating'])
        * (home['PlaysGame'] * (away['dPlaysGame'] / 68))
        / ((away['wdYdsPt'] + home['wYdsPt']) / 2)
        + home_adv + 1.74
    )
    away_score = (
        (0.5 * away['wYdsPlay'] * home['dRating'] + 0.5 * home['wdYdsPlay'] * away['oRating'])
        * (away['PlaysGame'] * (home['dPlaysGame'] / 68))
        / ((home['wdYdsPt'] + away['wYdsPt']) / 2)
        - home_adv + 1.74
    )
    return round(home_score, 2), round(away_score, 2)


def win_prob(diff: float) -> float:
    return round(1 / (1 + math.exp(-0.12 * diff)), 3)


def confidence_label(edge: float) -> str:
    if edge >= 0.18: return 'Elite'
    if edge >= 0.10: return 'Strong'
    if edge >= 0.05: return 'Lean'
    return ''


def fetch_schedule(year: int, weeks: list) -> list:
    if not API_KEY:
        print('[NCAAF] CFBD_API_KEY not set — no schedule available.')
        return []
    headers = {'Authorization': f'Bearer {API_KEY}'}
    games   = []
    seen    = set()
    for week in weeks:
        try:
            resp = requests.get(
                f'{BASE}/games',
                params={'year': year, 'week': week, 'seasonType': 'regular'},
                headers=headers, timeout=15,
            )
            if resp.status_code == 200:
                for g in resp.json():
                    gid = g.get('id')
                    if gid not in seen:
                        seen.add(gid)
                        games.append(g)
            time.sleep(0.3)
        except Exception as exc:
            print(f'[NCAAF] Schedule w{week} error: {exc}')
    print(f'[NCAAF] Fetched {len(games)} games for weeks {weeks}.')
    return games


def current_ncaaf_weeks(now: datetime) -> list:
    """Return [prev_week, current_week, next_week] based on today's date.
    Previous week included so Sunday/Monday runs capture last week's results."""
    start_of_week0 = datetime(now.year, 8, 24, tzinfo=timezone.utc)
    days_in        = max(0, (now - start_of_week0).days)
    current_week   = days_in // 7
    prev_week      = max(0, current_week - 1)
    next_week      = current_week + 1
    weeks = sorted(set([prev_week, current_week, next_week]))
    return weeks


def save_to_firestore(games_data: list):
    """Save/update NCAAF game predictions and actual scores in Firestore."""
    if not SA_JSON:
        print('[NCAAF] FIREBASE_SERVICE_ACCOUNT not set — skipping Firestore.')
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[NCAAF] firebase-admin not installed — skipping Firestore.')
        return

    try:
        cred = credentials.Certificate(json.loads(SA_JSON))
        app  = firebase_admin.initialize_app(cred, name='ncaaf_picks')
        db   = fb_firestore.client(app)

        created = updated = skipped = 0
        for entry in games_data:
            doc_id  = f'ncaaf_{entry["gameId"]}'
            doc_ref = db.collection('games').document(doc_id)
            existing = doc_ref.get()

            actual_home = entry.get('actualHomeScore')
            actual_away = entry.get('actualAwayScore')

            if existing.exists:
                # Update actual scores if game just finished
                if actual_home is not None and existing.to_dict().get('actualHomeScore') is None:
                    doc_ref.update({
                        'actualHomeScore': actual_home,
                        'actualAwayScore': actual_away,
                    })
                    print(f'  [Updated] {entry["awayTeam"]} @ {entry["homeTeam"]}: {actual_away}-{actual_home}')
                    updated += 1
                else:
                    skipped += 1
            else:
                doc_ref.set({
                    'sport':              'NCAAF',
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
        print(f'[NCAAF] Firestore: {created} created, {updated} updated, {skipped} skipped.')
    except Exception as exc:
        print(f'[NCAAF] Firestore error: {exc}')


def generate_ncaaf_picks():
    stats = load_stats()
    if not stats:
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return

    now        = datetime.now(timezone.utc)
    year       = now.year if now.month >= 8 else now.year - 1
    weeks      = current_ncaaf_weeks(now)
    games      = fetch_schedule(year, weeks)
    window_end = now + timedelta(days=7)

    picks         = []   # upcoming games with clear edge → ncaaf-picks.json
    firestore_data = []  # all simulatable games → Firestore
    skipped       = 0

    for g in games:
        game_id   = g.get('id')
        start_raw = g.get('start_date', '')
        home      = CFBD_TO_CSV.get(g.get('home_team', ''), g.get('home_team', ''))
        away      = CFBD_TO_CSV.get(g.get('away_team', ''), g.get('away_team', ''))
        h_pts     = g.get('home_points')
        a_pts     = g.get('away_points')

        h_stats = stats.get(home)
        a_stats = stats.get(away)
        if not h_stats or not a_stats:
            skipped += 1
            continue

        try:
            game_dt = datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            skipped += 1
            continue

        h_score, a_score = simulate(h_stats, a_stats)
        diff  = h_score - a_score
        wp    = win_prob(diff)

        if wp >= 0.5:
            pick_team, pick_wp = home, wp
        else:
            pick_team, pick_wp = away, 1 - wp

        edge  = pick_wp - 0.5
        label = confidence_label(edge)

        entry = {
            'gameId':             game_id,
            'homeTeam':           home,
            'awayTeam':           away,
            'predictedHomeScore': h_score,
            'predictedAwayScore': a_score,
            'pick':               pick_team,
            'winProb':            round(pick_wp, 3),
            'confidence':         label,
            'gameTime':           start_raw,
            'actualHomeScore':    int(h_pts) if h_pts is not None else None,
            'actualAwayScore':    int(a_pts) if a_pts is not None else None,
        }
        firestore_data.append(entry)

        # Add to picks list only if upcoming with a clear edge
        if h_pts is None and game_dt >= now and game_dt <= window_end and label:
            picks.append(entry)

    picks.sort(key=lambda p: p['winProb'], reverse=True)
    for i, p in enumerate(picks):
        p['rank'] = i + 1

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)
    print(f'[NCAAF] {len(picks)} picks saved → {OUTPUT}  ({skipped} skipped)')

    save_to_firestore(firestore_data)


if __name__ == '__main__':
    generate_ncaaf_picks()
