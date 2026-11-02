"""
Generate NCAA Men's Basketball picks and write ncaam-picks.json.
Also saves predictions to Firestore (Results page).

Schedule source: ESPN DI scoreboard (groups=50, no auth required).
Stats source:    NCAAM-Stats.csv (written daily by fetch_ncaam_stats.py).

Simulation mirrors scoreboard.component.ts NCAAM case:
  averageAdjT = homeTeam.adjT * awayTeam.TRank
  homeScore   = floor(((homeTeam.adjO * awayTeam.DRank) / 100) * averageAdjT + HomeAdv/2 + 0.7)
  awayScore   = floor(((awayTeam.adjO * homeTeam.DRank) / 100) * averageAdjT - HomeAdv/2 + 0.7)

Win probability (mirrors scoreboard.component.ts NCAAM):
  winProb = 0.495911 + 0.02832 * abs(scoreDiff)   (capped at 0.99)
"""

import csv
import json
import math
import os
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_PATH = os.path.join(ASSETS, 'NCAAM-Stats.csv')
OUTPUT     = os.path.join(ASSETS, 'ncaam-picks.json')
SA_JSON    = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
ET         = ZoneInfo('America/New_York')

# ESPN shortDisplayName → NCAAM-Stats.csv Team name
ESPN_TO_CSV = {
    'Abilene Chrstn':   'Abilene Christian',
    'Alcorn St':        'Alcorn St.',
    'App State':        'Appalachian St.',
    'Arizona St':       'Arizona St.',
    'Arkansas St':      'Arkansas St.',
    'Ball State':       'Ball St.',
    'Bethune':          'Bethune Cookman',
    'Boston U':         'Boston University',
    'BYU':              'Brigham Young',
    'C Arkansas':       'Central Arkansas',
    'C Connecticut':    'Central Connecticut',
    'C Michigan':       'Central Michigan',
    'Charleston So':    'Charleston Southern',
    'Chicago St':       'Chicago St.',
    'Coastal':          'Coastal Carolina',
    'Colorado St':      'Colorado St.',
    'Delaware St':      'Delaware St.',
    'E Illinois':       'Eastern Illinois',
    'E Kentucky':       'Eastern Kentucky',
    'E Michigan':       'Eastern Michigan',
    'E Washington':     'Eastern Washington',
    'ETSU':             'East Tennessee St.',
    'FAU':              'Florida Atlantic',
    'FDU':              'Fairleigh Dickinson',
    'FGCU':             'Florida Gulf Coast',
    'Florida St':       'Florida St.',
    'Fresno St':        'Fresno St.',
    'G Washington':     'George Washington',
    'GA Southern':      'Georgia Southern',
    'Gardner-Webb':     'Gardner Webb',
    'Georgia St':       'Georgia St.',
    'Grambling':        'Grambling St.',
    "Hawai'i":          'Hawaii',
    'Idaho St':         'Idaho St.',
    'Illinois St':      'Illinois St.',
    'Indiana St':       'Indiana St.',
    'Iowa State':       'Iowa St.',
    'Jackson St':       'Jackson St.',
    'Jax State':        'Jacksonville St.',
    'Kennesaw St':      'Kennesaw St.',
    'Kent State':       'Kent St.',
    'Long Beach St':    'Long Beach St.',
    'Long Island':      'Long Island University',
    'MD Eastern':       'Maryland-Eastern Shore',
    'Miami':            'Miami FL',
    'Michigan St':      'Michigan St.',
    'Mississippi St':   'Mississippi St.',
    'Montana St':       'Montana St.',
    'Morehead St':      'Morehead St.',
    'Morgan St':        'Morgan St.',
    'Mount St Marys':   "Mount St. Mary's",
    'MTSU':             'Middle Tennessee',
    'Murray St':        'Murray St.',
    'N Colorado':       'Northern Colorado',
    'N Illinois':       'Northern Illinois',
    'N Kentucky':       'Northern Kentucky',
    'Norfolk St':       'Norfolk St.',
    'Ohio State':       'Ohio St.',
    'Oklahoma St':      'Oklahoma St.',
    'Omaha':            'Nebraska Omaha',
    'Oregon St':        'Oregon St.',
    'Penn State':       'Penn St.',
    'Pitt':             'Pittsburgh',
    'Prairie View':     'Prairie View A&M',
    'Sacramento St':    'Sacramento St.',
    'San Jose St':      'San Jose St.',
    'Santa Barbara':    'UC Santa Barbara',
    'SC Upstate':       'USC Upstate',
    'Seattle U':        'Seattle',
    'Tarleton St':      'Tarleton St.',
    'Tennessee St':     'Tennessee St.',
    'Texas A&M-CC':     'Texas A&M Corpus Chris',
    'Texas St':         'Texas St.',
    'UAB':              'Alabama-Birmingham',
    'USC':              'Southern California',
    'UT Rio Grande':    'UT Rio Grande Valley',
    'UTEP':             'Texas-El Paso',
    'UTSA':             'UT San Antonio',
    'Utah State':       'Utah St.',
    'Washington St':    'Washington St.',
    'Weber St':         'Weber St.',
    'Western KY':       'Western Kentucky',
    'Wright St':        'Wright St.',
    'Youngstown St':    'Youngstown St.',
}


def load_stats() -> dict:
    stats = {}
    if not os.path.exists(STATS_PATH):
        print('[NCAAM Picks] NCAAM-Stats.csv not found.')
        return stats
    with open(STATS_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                team = row['Team'].strip()
                stats[team] = {
                    'adjO':    float(row['AdjO']),
                    'adjD':    float(row['AdjD']),
                    'adjT':    float(row['AdjT']),
                    'ORank':   float(row['Orank']),
                    'DRank':   float(row['Drank']),
                    'TRank':   float(row['Trank']),
                    'HomeAdv': float(row['HomeAdv']),
                }
            except (ValueError, KeyError):
                continue
    print(f'[NCAAM Picks] Loaded stats for {len(stats)} teams.')
    return stats


def resolve_name(espn_short: str) -> str:
    return ESPN_TO_CSV.get(espn_short, espn_short)


def fetch_schedule(dates: list[str]) -> list:
    games = []
    seen  = set()
    for date_str in dates:
        compact = date_str.replace('-', '')
        url = (f'https://site.api.espn.com/apis/site/v2/sports/basketball'
               f'/mens-college-basketball/scoreboard?dates={compact}&groups=50&limit=300')
        try:
            resp = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                print(f'[NCAAM Picks] ESPN {date_str}: HTTP {resp.status_code}')
                continue
            for event in resp.json().get('events', []):
                eid = event.get('id')
                if eid not in seen:
                    seen.add(eid)
                    games.append(event)
            time.sleep(0.3)
        except Exception as exc:
            print(f'[NCAAM Picks] ESPN {date_str} error: {exc}')
    print(f'[NCAAM Picks] Fetched {len(games)} total events')
    return games


def parse_event(event: dict) -> dict | None:
    comp        = (event.get('competitions') or [{}])[0]
    competitors = comp.get('competitors', [])
    if len(competitors) < 2:
        return None
    home_comp = next((c for c in competitors if c.get('homeAway') == 'home'), None)
    away_comp = next((c for c in competitors if c.get('homeAway') == 'away'), None)
    if not home_comp or not away_comp:
        return None

    home_espn = (home_comp.get('team') or {}).get('shortDisplayName', '')
    away_espn = (away_comp.get('team') or {}).get('shortDisplayName', '')
    home_name = resolve_name(home_espn)
    away_name = resolve_name(away_espn)

    start_utc = event.get('date', '')
    status    = (comp.get('status') or {}).get('type', {})
    is_final  = status.get('completed', False)
    home_score = away_score = None
    if is_final:
        try:
            home_score = int(home_comp.get('score', 0))
            away_score = int(away_comp.get('score', 0))
        except (TypeError, ValueError):
            pass

    return {
        'gameId':     event.get('id'),
        'homeTeam':   home_name,
        'awayTeam':   away_name,
        'startUTC':   start_utc,
        'isFinal':    is_final,
        'homeActual': home_score,
        'awayActual': away_score,
    }


def simulate(home: dict, away: dict) -> tuple[int, int]:
    avg_t      = home['adjT'] * away['TRank']
    home_adv   = home['HomeAdv'] / 2
    home_score = math.floor(((home['adjO'] * away['DRank']) / 100) * avg_t + home_adv + 0.7)
    away_score = math.floor(((away['adjO'] * home['DRank']) / 100) * avg_t - home_adv + 0.7)
    return home_score, away_score


def win_prob(score_diff: int) -> float:
    return min(0.99, 0.495911 + 0.02832 * abs(score_diff))


def confidence_label(wp: float) -> str:
    edge = wp - 0.5
    if edge >= 0.18: return 'Elite'
    if edge >= 0.10: return 'Strong'
    if edge >= 0.05: return 'Lean'
    return ''


def save_to_firestore(picks_data: list):
    if not SA_JSON:
        print('[NCAAM Picks] FIREBASE_SERVICE_ACCOUNT not set -- skipping Firestore.')
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[NCAAM Picks] firebase-admin not installed -- skipping Firestore.')
        return
    try:
        cred = credentials.Certificate(json.loads(SA_JSON))
        app  = firebase_admin.initialize_app(cred, name='ncaam_picks')
        db   = fb_firestore.client(app)
        now_utc = datetime.now(timezone.utc)
        created = updated = skipped = 0

        for p in picks_data:
            home     = p['homeTeam']
            away     = p['awayTeam']
            gt       = p.get('gameTime', '')
            date_str = gt[:10] if gt else ''
            h_norm   = home.replace(' ', '_').replace("'", '').replace('.', '')
            a_norm   = away.replace(' ', '_').replace("'", '').replace('.', '')
            doc_id   = f'ncaam_{h_norm}_{a_norm}_{date_str}'
            doc_ref  = db.collection('games').document(doc_id)
            existing = doc_ref.get()

            actual_home = p.get('actualHomeScore')
            actual_away = p.get('actualAwayScore')

            prediction_locked = False
            if gt:
                try:
                    game_dt = datetime.fromisoformat(gt.replace('Z', '+00:00'))
                    prediction_locked = (game_dt - now_utc).total_seconds() < 24 * 3600
                except ValueError:
                    pass

            if existing.exists:
                existing_data = existing.to_dict()
                if actual_home is not None and existing_data.get('actualHomeScore') is None:
                    doc_ref.update({'actualHomeScore': actual_home, 'actualAwayScore': actual_away})
                    updated += 1
                elif existing_data.get('actualHomeScore') is None and not prediction_locked:
                    doc_ref.update({
                        'predictedHomeScore': p['predictedHomeScore'],
                        'predictedAwayScore': p['predictedAwayScore'],
                        'pick':               p.get('pick', ''),
                        'winProb':            p.get('winProb', 0),
                        'confidence':         p.get('confidence', ''),
                    })
                    updated += 1
                else:
                    skipped += 1
            else:
                doc_ref.set({
                    'sport':              'NCAAM',
                    'homeTeam':           home,
                    'awayTeam':           away,
                    'predictedHomeScore': p['predictedHomeScore'],
                    'predictedAwayScore': p['predictedAwayScore'],
                    'actualHomeScore':    actual_home,
                    'actualAwayScore':    actual_away,
                    'pick':               p.get('pick', ''),
                    'winProb':            p.get('winProb', 0),
                    'confidence':         p.get('confidence', ''),
                    'gameTime':           gt,
                    'gameDate':           date_str,
                    'timestamp':          fb_firestore.SERVER_TIMESTAMP,
                })
                created += 1

        firebase_admin.delete_app(app)
        print(f'[NCAAM Picks] Firestore: {created} created, {updated} updated, {skipped} skipped.')
    except Exception as exc:
        print(f'[NCAAM Picks] Firestore error: {exc}')


def main():
    stats = load_stats()
    if not stats:
        print('[NCAAM Picks] No stats -- aborting.')
        sys.exit(1)

    now    = datetime.now(timezone.utc)
    now_et = now.astimezone(ET)
    # Yesterday + today + next 2 days (yesterday for score backfill)
    et_dates = [(now_et + timedelta(days=d)).strftime('%Y-%m-%d') for d in range(-1, 3)]

    raw_events = fetch_schedule(et_dates)
    picks          = []
    firestore_data = []
    skipped        = 0

    for event in raw_events:
        parsed = parse_event(event)
        if not parsed:
            skipped += 1
            continue

        home_name = parsed['homeTeam']
        away_name = parsed['awayTeam']
        h_stats   = stats.get(home_name)
        a_stats   = stats.get(away_name)
        if not h_stats or not a_stats:
            skipped += 1
            continue

        h_score, a_score = simulate(h_stats, a_stats)
        diff = h_score - a_score
        wp   = win_prob(diff)
        if diff >= 0:
            pick_team, pick_wp = home_name, wp
        else:
            pick_team, pick_wp = away_name, wp
        label = confidence_label(pick_wp)

        entry = {
            'homeTeam':           home_name,
            'awayTeam':           away_name,
            'predictedHomeScore': h_score,
            'predictedAwayScore': a_score,
            'actualHomeScore':    parsed['homeActual'],
            'actualAwayScore':    parsed['awayActual'],
            'pick':               pick_team,
            'winProb':            round(pick_wp, 3),
            'confidence':         label,
            'gameTime':           parsed['startUTC'],
        }
        firestore_data.append(entry)

        game_started = parsed['startUTC'] and (
            datetime.fromisoformat(parsed['startUTC'].replace('Z', '+00:00')) <= now
        )
        if not game_started and label:
            picks.append(entry)

    picks.sort(key=lambda p: p['winProb'], reverse=True)
    for i, p in enumerate(picks):
        p['rank'] = i + 1

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)
    print(f'[NCAAM Picks] Wrote {len(picks)} upcoming picks -> {OUTPUT}  ({skipped} events skipped)')

    save_to_firestore(firestore_data)


if __name__ == '__main__':
    main()
