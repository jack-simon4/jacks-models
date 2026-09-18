"""
Generate NFL game picks for the current week and write nfl-picks.json.
Uses NFL-Stats.csv (team ratings), NFL-QBs.csv, NFL-RBs.csv, and NFL-Spreads.csv.

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
QB_PATH    = os.path.join(ASSETS, 'NFL-QBs.csv')
RB_PATH    = os.path.join(ASSETS, 'NFL-RBs.csv')
SPREAD_PATH= os.path.join(ASSETS, 'NFL-Spreads.csv')
OUT_PATH   = os.path.join(ASSETS, 'nfl-picks.json')

SA_JSON    = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
WIN_PROB_K = 0.30


def load_stats() -> dict:
    stats = {}
    with open(STATS_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                stats[row['Team'].strip()] = {
                    'RushYdsAtt':   float(row['RushYdsAtt']),
                    'dRushYdsAtt':  float(row['dRushYdsAtt']),
                    'PassYdsAtt':   float(row['PassYdsAtt']),
                    'dPassYdsAtt':  float(row['dPassYdsAtt']),
                    'oRushPerGame': float(row['oRushPerGame']),
                    'dRushPerGame': float(row['dRushPerGame']),
                    'oPassPerGame': float(row['oPassPerGame']),
                    'dPassPerGame': float(row['dPassPerGame']),
                    'oYdsPerPoint': float(row['oYdsPerPoint']),
                    'dYdsPerPoint': float(row['dYardsPerPoint']),
                    'oPtsPerPlay':  float(row['oPtsPerPlay']),
                    'dPtsPerPlay':  float(row['dPtsPerPlay']),
                    'oPlaysGame':   float(row['oPlays/Game']),
                    'dPlaysGame':   float(row['dPlaysGame']),
                    'HomeAdv':      float(row['HomeAdv']),
                }
            except (ValueError, KeyError):
                pass
    return stats


def load_league_avg(stats: dict) -> dict:
    teams = list(stats.values())
    def avg(key): return sum(t[key] for t in teams) / len(teams)
    return {
        'rushYPA': avg('RushYdsAtt'),
        'rushAtt': avg('oRushPerGame'),
        'passYPA': avg('PassYdsAtt'),
        'passAtt': avg('oPassPerGame'),
        'ydsPt':   avg('oYdsPerPoint'),
        'ptsPP':   avg('oPtsPerPlay'),
        'playsG':  avg('oPlaysGame'),
    }


def load_qbs() -> dict:
    qbs = {}
    try:
        with open(QB_PATH, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                team = row['Team'].strip()
                qbs[team] = {
                    'passYdsAtt':  float(row['PassYdsAtt']),
                    'passAttGame': float(row['PassAttGame']),
                }
    except FileNotFoundError:
        print('[NFL Picks] NFL-QBs.csv not found — using team averages for passing.')
    return qbs


def load_rbs() -> dict:
    rbs: dict = {}
    try:
        with open(RB_PATH, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                team = row['Team'].strip()
                if team not in rbs:
                    rbs[team] = []
                rbs[team].append({
                    'rushYdsCarry': float(row['RushYdsCarry']),
                    'rushAttGame':  float(row['RushAttGame']),
                })
    except FileNotFoundError:
        print('[NFL Picks] NFL-RBs.csv not found — using team averages for rushing.')
    return rbs


def weighted_ypc(rbs: list, fallback: float) -> float:
    total_att = sum(rb['rushAttGame'] for rb in rbs)
    if total_att > 0:
        return sum(rb['rushYdsCarry'] * rb['rushAttGame'] for rb in rbs) / total_att
    return fallback


def simulate(home: dict, away: dict, lg: dict,
             home_qb: dict | None, away_qb: dict | None,
             home_rbs: list, away_rbs: list) -> tuple[float, float]:
    """Mirror the Angular NFL simulation formula in scoreboard.component.ts."""
    home_adv = home['HomeAdv'] / 2

    h_pass_ypa = home_qb['passYdsAtt']  if home_qb else home['PassYdsAtt']
    h_pass_apg = home_qb['passAttGame'] if home_qb else home['oPassPerGame']
    a_pass_ypa = away_qb['passYdsAtt']  if away_qb else away['PassYdsAtt']
    a_pass_apg = away_qb['passAttGame'] if away_qb else away['oPassPerGame']

    h_rush_ypc = weighted_ypc(home_rbs, home['RushYdsAtt'])
    a_rush_ypc = weighted_ypc(away_rbs, away['RushYdsAtt'])

    # Rush yards
    hr_yds_att = .85 * h_rush_ypc          * (away['dRushYdsAtt'] / lg['rushYPA']) + .15 * lg['rushYPA']
    ar_yds_att = .85 * a_rush_ypc          * (home['dRushYdsAtt'] / lg['rushYPA']) + .15 * lg['rushYPA']
    hr_att     = .85 * home['oRushPerGame'] * (away['dRushPerGame'] / lg['rushAtt']) + .15 * lg['rushAtt']
    ar_att     = .85 * away['oRushPerGame'] * (home['dRushPerGame'] / lg['rushAtt']) + .15 * lg['rushAtt']
    h_rush_yds = hr_yds_att * hr_att
    a_rush_yds = ar_yds_att * ar_att

    # Pass yards
    hp_yds_att = .85 * h_pass_ypa * (away['dPassYdsAtt'] / lg['passYPA']) + .15 * lg['passYPA']
    ap_yds_att = .85 * a_pass_ypa * (home['dPassYdsAtt'] / lg['passYPA']) + .15 * lg['passYPA']
    hp_att     = .85 * h_pass_apg * (away['dPassPerGame'] / lg['passAtt']) + .15 * lg['passAtt']
    ap_att     = .85 * a_pass_apg * (home['dPassPerGame'] / lg['passAtt']) + .15 * lg['passAtt']
    h_pass_yds = hp_yds_att * hp_att
    a_pass_yds = ap_yds_att * ap_att

    h_total_yds = h_pass_yds + h_rush_yds
    a_total_yds = a_pass_yds + a_rush_yds

    # Yards-based score
    h_oyp = .85 * home['oYdsPerPoint'] * (away['dYdsPerPoint'] / lg['ydsPt']) + .15 * lg['ydsPt']
    a_oyp = .85 * away['oYdsPerPoint'] * (home['dYdsPerPoint'] / lg['ydsPt']) + .15 * lg['ydsPt']
    h_yds_score = h_total_yds / h_oyp
    a_yds_score = a_total_yds / a_oyp

    # Plays-based score
    h_ppp = .85 * home['oPtsPerPlay'] * (away['dPtsPerPlay'] / lg['ptsPP']) + .15 * lg['ptsPP']
    a_ppp = .85 * away['oPtsPerPlay'] * (home['dPtsPerPlay'] / lg['ptsPP']) + .15 * lg['ptsPP']
    h_plg = .85 * home['oPlaysGame']  * (away['dPlaysGame']  / lg['playsG']) + .15 * lg['playsG']
    a_plg = .85 * away['oPlaysGame']  * (home['dPlaysGame']  / lg['playsG']) + .15 * lg['playsG']
    h_plays_score = h_ppp * h_plg
    a_plays_score = a_ppp * a_plg

    h_score = round(((h_yds_score + h_plays_score) / 2) + home_adv, 2)
    a_score = round(((a_yds_score + a_plays_score) / 2) - home_adv, 2)
    return h_score, a_score


def win_prob(diff: float) -> float:
    return round(1 / (1 + math.exp(-WIN_PROB_K * diff)), 3)


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

    lg   = load_league_avg(stats)
    qbs  = load_qbs()
    rbs  = load_rbs()

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

        h_score, a_score = simulate(
            home_stats, away_stats, lg,
            qbs.get(home_name), qbs.get(away_name),
            rbs.get(home_name, []), rbs.get(away_name, []),
        )
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
