"""
Fetch actual NFL game scores via nfl_data_py and update Firestore predictions.
Runs Monday/Tuesday after Sunday/Monday games complete so the Results page
shows real final scores alongside predicted scores.
"""

import json
import os
import sys
from datetime import date

try:
    import nfl_data_py as nfl
except ImportError:
    print('[NFL Results] nfl-data-py not installed; skipping.')
    sys.exit(0)

SA_JSON = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')

# Matches abbreviations used by nfl_data_py schedule to full team names in Firestore
TEAM_NAMES = {
    'ARI': 'Arizona Cardinals',    'ATL': 'Atlanta Falcons',
    'BAL': 'Baltimore Ravens',     'BUF': 'Buffalo Bills',
    'CAR': 'Carolina Panthers',    'CHI': 'Chicago Bears',
    'CIN': 'Cincinnati Bengals',   'CLE': 'Cleveland Browns',
    'DAL': 'Dallas Cowboys',       'DEN': 'Denver Broncos',
    'DET': 'Detroit Lions',        'GB':  'Green Bay Packers',
    'HOU': 'Houston Texans',       'IND': 'Indianapolis Colts',
    'JAX': 'Jacksonville Jaguars', 'KC':  'Kansas City Chiefs',
    'LV':  'Las Vegas Raiders',    'LAC': 'Los Angeles Chargers',
    'LA':  'Los Angeles Rams',     'MIA': 'Miami Dolphins',
    'MIN': 'Minnesota Vikings',    'NE':  'New England Patriots',
    'NO':  'New Orleans Saints',   'NYG': 'New York Giants',
    'NYJ': 'New York Jets',        'PHI': 'Philadelphia Eagles',
    'PIT': 'Pittsburgh Steelers',  'SF':  'San Francisco 49ers',
    'SEA': 'Seattle Seahawks',     'TB':  'Tampa Bay Buccaneers',
    'TEN': 'Tennessee Titans',     'WAS': 'Washington Commanders',
}


def update_nfl_results():
    if not SA_JSON:
        print('[NFL Results] FIREBASE_SERVICE_ACCOUNT not set; skipping.')
        return

    today  = date.today()
    season = today.year if today.month >= 8 else today.year - 1

    try:
        sched = nfl.import_schedules([season])
    except Exception as exc:
        print(f'[NFL Results] Schedule fetch failed: {exc}')
        return

    # Regular season games with final scores
    finished = sched[
        (sched['game_type'] == 'REG') &
        sched['home_score'].notna() &
        sched['away_score'].notna()
    ]

    if finished.empty:
        print('[NFL Results] No finished regular season games yet.')
        return

    # Build lookup: (home_full_name, away_full_name) → (home_score, away_score)
    results = {}
    for _, row in finished.iterrows():
        home_name = TEAM_NAMES.get(row['home_team'], row['home_team'])
        away_name = TEAM_NAMES.get(row['away_team'], row['away_team'])
        results[(home_name, away_name)] = (int(row['home_score']), int(row['away_score']))

    print(f'[NFL Results] {len(results)} finished games found in schedule.')

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[NFL Results] firebase-admin not installed; skipping.')
        return

    try:
        cred = credentials.Certificate(json.loads(SA_JSON))
        app  = firebase_admin.initialize_app(cred, name='nfl_results')
        db   = fb_firestore.client(app)

        pending = [
            doc for doc in db.collection('games').where('sport', '==', 'NFL').stream()
            if doc.to_dict().get('actualHomeScore') is None
        ]
        print(f'[NFL Results] {len(pending)} pending NFL games in Firestore.')

        updated = 0
        for doc in pending:
            data = doc.to_dict()
            key  = (data.get('homeTeam', ''), data.get('awayTeam', ''))
            if key in results:
                h_score, a_score = results[key]
                doc.reference.update({
                    'actualHomeScore': h_score,
                    'actualAwayScore': a_score,
                })
                print(f'  [Updated] {key[1]} @ {key[0]}: {a_score}-{h_score}')
                updated += 1

        firebase_admin.delete_app(app)
        print(f'[NFL Results] Done. Updated {updated} game(s).')
    except Exception as exc:
        print(f'[NFL Results] Firestore error: {exc}')


if __name__ == '__main__':
    update_nfl_results()
