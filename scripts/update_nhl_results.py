"""
Fetch NHL game scores from the NHL API and update Firestore predictions.
Runs daily to fill in actual scores for completed games so they appear
on the Results page.
"""

import json
import os
import requests
from datetime import datetime, timedelta, timezone

SA_JSON    = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
SCORE_BASE = 'https://api-web.nhle.com/v1/score'


def fetch_scores(date_str: str) -> list:
    try:
        resp = requests.get(f'{SCORE_BASE}/{date_str}', timeout=15)
        resp.raise_for_status()
        return resp.json().get('games', [])
    except Exception as exc:
        print(f'[NHL Results] Score fetch error for {date_str}: {exc}')
        return []


def update_nhl_results():
    if not SA_JSON:
        print('[NHL Results] FIREBASE_SERVICE_ACCOUNT not set — skipping.')
        return

    now = datetime.now(timezone.utc)
    # Check the last 3 days to catch any games that finished recently
    dates = [(now - timedelta(days=d)).strftime('%Y-%m-%d') for d in range(1, 4)]

    # game_id → (home_score, away_score) for all final games
    score_lookup: dict = {}
    for date_str in dates:
        for g in fetch_scores(date_str):
            if g.get('gameState') in ('FINAL', 'OFF', 'CRIT'):
                gid = g.get('id')
                h   = (g.get('homeTeam') or {}).get('score')
                a   = (g.get('awayTeam') or {}).get('score')
                if gid and h is not None and a is not None:
                    score_lookup[gid] = (int(h), int(a))
    print(f'[NHL Results] {len(score_lookup)} final games found in the last 3 days.')

    if not score_lookup:
        print('[NHL Results] No completed games — nothing to update.')
        return

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[NHL Results] firebase-admin not installed — skipping.')
        return

    try:
        cred = credentials.Certificate(json.loads(SA_JSON))
        app  = firebase_admin.initialize_app(cred, name='nhl_results')
        db   = fb_firestore.client(app)

        pending = [
            doc for doc in db.collection('games').where('sport', '==', 'NHL').stream()
            if doc.to_dict().get('actualHomeScore') is None
        ]
        print(f'[NHL Results] {len(pending)} pending NHL games in Firestore.')

        updated = 0
        for doc in pending:
            data = doc.to_dict()
            gid  = data.get('gameId')
            if gid in score_lookup:
                h_score, a_score = score_lookup[gid]
                doc.reference.update({
                    'actualHomeScore': h_score,
                    'actualAwayScore': a_score,
                })
                print(f'  [Updated] {data.get("awayTeam")} @ {data.get("homeTeam")}: {a_score}-{h_score}')
                updated += 1

        firebase_admin.delete_app(app)
        print(f'[NHL Results] Done. Updated {updated} game(s).')
    except Exception as exc:
        print(f'[NHL Results] Firestore error: {exc}')


if __name__ == '__main__':
    update_nhl_results()
