"""
Fetch actual MLB game results and update Firestore predictions.

Reads all MLB games in the 'games' collection where actualHomeScore is null,
checks statsapi for final scores, and writes them back so the results tab
shows real W/L outcomes.

Runs hourly alongside fetch_mlb_lineups.py.
"""

import json
import os
import sys

import statsapi

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fb_firestore
except ImportError:
    print('[Results] firebase-admin not installed; skipping.')
    sys.exit(0)


def update_results():
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        print('[Results] FIREBASE_SERVICE_ACCOUNT not set; skipping.')
        return

    cred = credentials.Certificate(json.loads(sa_json))
    app = firebase_admin.initialize_app(cred)
    db = fb_firestore.client()

    # Fetch all MLB games, filter pending ones in Python to avoid index requirements
    all_games = db.collection('games').where('sport', '==', 'MLB').stream()
    pending = [doc for doc in all_games if doc.to_dict().get('actualHomeScore') is None]
    print(f'[Results] {len(pending)} pending MLB games to check.')

    updated = 0
    for doc in pending:
        data = doc.to_dict()
        game_pk = data.get('gamePk')
        away = data.get('awayTeam', '?')
        home = data.get('homeTeam', '?')

        if not game_pk:
            print(f'  [Skip] {away} @ {home} — no gamePk stored.')
            continue

        try:
            result = statsapi.schedule(game_id=game_pk)
        except Exception as exc:
            print(f'  [Error] gamePk {game_pk}: {exc}')
            continue

        if not result:
            print(f'  [Skip] gamePk {game_pk} — no data returned.')
            continue

        game = result[0]
        status = game.get('status', '')

        if status not in ('Final', 'Game Over', 'Completed Early'):
            print(f'  [Pending] {away} @ {home} — {status}')
            continue

        home_score = game.get('home_score')
        away_score = game.get('away_score')

        if home_score is None or away_score is None:
            print(f'  [Skip] {away} @ {home} — scores missing in response.')
            continue

        doc.reference.update({
            'actualHomeScore': int(home_score),
            'actualAwayScore': int(away_score),
        })
        print(f'  [Updated] {away} @ {home}: {away_score}-{home_score}')
        updated += 1

    firebase_admin.delete_app(app)
    print(f'[Results] Done. Updated {updated} game(s).')


if __name__ == '__main__':
    update_results()
