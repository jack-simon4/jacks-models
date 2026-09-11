"""
Generate NFL game picks for the current week and write nfl-picks.json.
Uses NFL-Stats.csv (team ratings) and NFL-Spreads.csv (matchups + lines).

NFL-Spreads.csv format: Team, Spread, Opponent, GameTime (UTC)
  Spread is from the team's perspective (negative = favorite).
  If Opponent/GameTime columns are absent the script skips that row.

Output: src/assets/nfl-picks.json
  List of game objects:
  { homeTeam, awayTeam, homePredicted, awayPredicted,
    predictedHomeScore, predictedAwayScore,
    pick, winProb, spread, gameTime, confidence }

Also saves predictions to Firestore (games collection) so they appear
on the Results page. Actual scores are filled in later by
update_nfl_results.py after games complete.
"""

import csv
import json
import math
import os

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_PATH = os.path.join(ASSETS, 'NFL-Stats.csv')
SPREAD_PATH= os.path.join(ASSETS, 'NFL-Spreads.csv')
OUT_PATH   = os.path.join(ASSETS, 'nfl-picks.json')

SA_JSON    = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
HOME_ADV   = 2.5   # points
WIN_PROB_K = 0.30


def load_stats() -> dict:
    stats = {}
    with open(STATS_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                # Derive PPG from per-play rate × plays-per-game when direct columns absent
                off_ppp   = float(row.get('oPtsPerPlay', 0) or 0)
                off_plays = float(row.get('oPlays/Game', 0) or 0)
                def_ppp   = float(row.get('dPtsPerPlay', 0) or 0)
                def_plays = float(row.get('dPlaysGame',  0) or 0)
                offPPG = float(row.get('offPPG', row.get('OffPPG', 0)) or 0) or round(off_ppp * off_plays, 2)
                defPPG = float(row.get('defPPG', row.get('DefPPG', 0)) or 0) or round(def_ppp * def_plays, 2)
                stats[row['Team']] = {
                    'offPPG': offPPG,
                    'defPPG': defPPG,
                    'offYPG': float(row.get('offYPG', row.get('OffYPG', 0)) or 0),
                    'defYPG': float(row.get('defYPG', row.get('DefYPG', 0)) or 0),
                }
            except (ValueError, KeyError):
                pass
    return stats


def load_spreads() -> list:
    matchups = []
    with open(SPREAD_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        has_opponent  = 'Opponent' in fieldnames
        if not has_opponent:
            return []  # old format without matchup data
        for row in reader:
            try:
                matchups.append({
                    'team':     row['Team'].strip(),
                    'spread':   float(row['Spread']),
                    'opponent': row['Opponent'].strip(),
                    'gameTime': row.get('GameTime', '').strip(),
                    'isHome':   row.get('IsHome', 'true').strip().lower() in ('true', '1', 'yes'),
                })
            except (ValueError, KeyError):
                pass
    return matchups


def simulate(home: dict, away: dict) -> tuple[float, float]:
    lg_avg_ppg = 23.0
    home_off = home['offPPG'] / lg_avg_ppg
    home_def = home['defPPG'] / lg_avg_ppg
    away_off = away['offPPG'] / lg_avg_ppg
    away_def = away['defPPG'] / lg_avg_ppg
    home_score = round(lg_avg_ppg * home_off / away_def + HOME_ADV / 2, 1)
    away_score = round(lg_avg_ppg * away_off / home_def - HOME_ADV / 2, 1)
    return home_score, away_score


def win_prob(diff: float) -> float:
    return round(1 / (1 + math.exp(-WIN_PROB_K * diff)), 3)


def save_to_firestore(picks: list):
    """Save NFL game predictions to Firestore. Skips docs that already exist."""
    if not SA_JSON:
        print('[NFL Picks] FIREBASE_SERVICE_ACCOUNT not set — skipping Firestore.')
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[NFL Picks] firebase-admin not installed — skipping Firestore.')
        return

    try:
        cred = credentials.Certificate(json.loads(SA_JSON))
        app  = firebase_admin.initialize_app(cred, name='nfl_picks')
        db   = fb_firestore.client(app)

        created = skipped = 0
        for p in picks:
            home     = p['homeTeam']
            away     = p['awayTeam']
            gt       = p.get('gameTime', '')
            date_str = gt[:10] if gt else ''
            h_norm   = home.replace(' ', '_').replace("'", '')
            a_norm   = away.replace(' ', '_').replace("'", '')
            doc_id   = f'nfl_{h_norm}_{a_norm}_{date_str}'
            doc_ref  = db.collection('games').document(doc_id)

            if doc_ref.get().exists:
                skipped += 1
                continue

            doc_ref.set({
                'sport':              'NFL',
                'homeTeam':           home,
                'awayTeam':           away,
                'predictedHomeScore': p['predictedHomeScore'],
                'predictedAwayScore': p['predictedAwayScore'],
                'actualHomeScore':    None,
                'actualAwayScore':    None,
                'pick':               p.get('pick', ''),
                'winProb':            p.get('winProb', 0),
                'spread':             p.get('spread', 0),
                'confidence':         p.get('confidence', ''),
                'gameTime':           gt,
                'gameDate':           date_str,
                'timestamp':          fb_firestore.SERVER_TIMESTAMP,
            })
            print(f'  [Saved] {away} @ {home}')
            created += 1

        firebase_admin.delete_app(app)
        print(f'[NFL Picks] Firestore: {created} created, {skipped} skipped.')
    except Exception as exc:
        print(f'[NFL Picks] Firestore error: {exc}')


def main():
    try:
        stats = load_stats()
    except FileNotFoundError:
        print('[NFL Picks] NFL-Stats.csv not found — skipping.')
        return

    try:
        matchups = load_spreads()
    except FileNotFoundError:
        print('[NFL Picks] NFL-Spreads.csv not found — skipping.')
        return

    if not matchups:
        print('[NFL Picks] NFL-Spreads.csv has no matchup data (needs Opponent column) — skipping.')
        json.dump([], open(OUT_PATH, 'w'))
        return

    seen   = set()
    picks  = []
    for m in matchups:
        if m['isHome']:
            home_name, away_name = m['team'], m['opponent']
        else:
            home_name, away_name = m['opponent'], m['team']

        key = tuple(sorted([home_name, away_name]))
        if key in seen:
            continue
        seen.add(key)

        home_stats = stats.get(home_name)
        away_stats = stats.get(away_name)
        if not home_stats or not away_stats:
            print(f'[NFL Picks] Missing stats for {home_name} or {away_name} — skipping.')
            continue

        h_score, a_score = simulate(home_stats, away_stats)
        diff  = h_score - a_score
        wp    = win_prob(diff)
        pick  = home_name if diff > 0 else away_name
        conf_pct = round((max(wp, 1 - wp)) * 100)
        confidence = 'Elite' if conf_pct >= 70 else ('Strong' if conf_pct >= 60 else 'Lean')
        pick_wp = wp if pick == home_name else round(1 - wp, 3)

        picks.append({
            'homeTeam':           home_name,
            'awayTeam':           away_name,
            'homePredicted':      h_score,      # kept for email compat
            'awayPredicted':      a_score,       # kept for email compat
            'predictedHomeScore': h_score,
            'predictedAwayScore': a_score,
            'pick':               pick,
            'winProb':            pick_wp,
            'spread':             m['spread'],
            'gameTime':           m['gameTime'],
            'confidence':         confidence,
        })

    picks.sort(key=lambda p: p['winProb'], reverse=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)
    print(f'[NFL Picks] Wrote {len(picks)} picks to nfl-picks.json.')

    save_to_firestore(picks)


if __name__ == '__main__':
    main()
