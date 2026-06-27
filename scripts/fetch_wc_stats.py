"""
Fetch 2026 FIFA World Cup results from football-data.org and:
  1. Update national team GF/GA in Soccer-Stats.csv (blended with pre-tournament)
  2. Save match predictions + actual scores to Firestore so the Results tab
     shows World Cup games alongside MLB picks.

Requires FOOTBALL_DATA_API_KEY and FIREBASE_SERVICE_ACCOUNT_JESIMON4_SCOREBOARD
GitHub secrets.

Blending: weight_actual = games_played / (games_played + PRIOR_GAMES)
  PRIOR_GAMES = 7  →  pre-tournament stats treated as 7 games of data.

Soccer model (port of TypeScript scoreboard, neutral site):
  homeScore = ((home.GF * away.wGA + home.wGF * away.GA) / 2)
              * (home.wLeague / away.wLeague)^2
  awayScore = ((away.GF * home.wGA + away.wGF * home.GA) / 2)
              * (away.wLeague / home.wLeague)^2
"""

import csv
import json
import math
import os
import sys
import time

import requests

API_KEY       = os.environ.get('FOOTBALL_DATA_API_KEY', '')
SA_JSON_STR   = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JESIMON4_SCOREBOARD', '')
BASE          = 'https://api.football-data.org/v4'

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
CSV_PATH = os.path.join(ASSETS, 'Soccer-Stats.csv')

PRIOR_GAMES    = 7
INTL_CONSTANT  = 1.3   # wGF = GF / 1.3 for all national teams

# Map football-data.org team names → our CSV names
FD_TO_CSV = {
    'Korea Republic':             'South Korea',
    "Côte d'Ivoire":              'Ivory Coast',
    'Ivory Coast':                'Ivory Coast',
    'Czech Republic':             'Czechia',
    'Turkey':                     'Türkiye',
    'Türkiye':                    'Türkiye',
    'DR Congo':                   'DR Congo',
    'Congo DR':                   'DR Congo',
    'Democratic Republic of Congo': 'DR Congo',
    'Bosnia and Herzegovina':     'Bosnia & Herzegovina',
    'Bosnia & Herzegovina':       'Bosnia & Herzegovina',
    'Curaçao':                    'Curaçao',
    'Curacao':                    'Curaçao',
    # Teams already matching
    'Algeria': 'Algeria', 'Argentina': 'Argentina', 'Australia': 'Australia',
    'Austria': 'Austria', 'Belgium': 'Belgium', 'Brazil': 'Brazil',
    'Canada': 'Canada', 'Cape Verde': 'Cape Verde', 'Colombia': 'Colombia',
    'Croatia': 'Croatia', 'Ecuador': 'Ecuador', 'Egypt': 'Egypt',
    'England': 'England', 'France': 'France', 'Germany': 'Germany',
    'Ghana': 'Ghana', 'Haiti': 'Haiti', 'Iran': 'Iran', 'Iraq': 'Iraq',
    'Japan': 'Japan', 'Jordan': 'Jordan', 'Mexico': 'Mexico',
    'Morocco': 'Morocco', 'Netherlands': 'Netherlands', 'New Zealand': 'New Zealand',
    'Norway': 'Norway', 'Panama': 'Panama', 'Paraguay': 'Paraguay',
    'Portugal': 'Portugal', 'Qatar': 'Qatar', 'Saudi Arabia': 'Saudi Arabia',
    'Scotland': 'Scotland', 'Senegal': 'Senegal', 'South Africa': 'South Africa',
    'Spain': 'Spain', 'Sweden': 'Sweden', 'Switzerland': 'Switzerland',
    'Tunisia': 'Tunisia', 'United States': 'United States', 'Uruguay': 'Uruguay',
    'Uzbekistan': 'Uzbekistan',
}


# ── API helper ────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> dict:
    resp = requests.get(
        f'{BASE}{endpoint}',
        headers={'X-Auth-Token': API_KEY},
        params=params or {},
        timeout=30,
    )
    if resp.status_code == 429:
        time.sleep(61)
        resp = requests.get(f'{BASE}{endpoint}',
                            headers={'X-Auth-Token': API_KEY},
                            params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── CSV helpers ───────────────────────────────────────────────────────────────

def load_stats() -> dict[str, dict]:
    """Load Soccer-Stats.csv → {team: {GF, GA, wGF, wGA, wLeague, HomeAdv}}"""
    stats = {}
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                stats[row['Team']] = {
                    'GF':       float(row['GF']),
                    'GA':       float(row['GA']),
                    'wGF':      float(row['wGF']),
                    'wGA':      float(row['wGA']),
                    'wLeague':  float(row['wLeague']),
                    'HomeAdv':  float(row['HomeAdv']),
                }
            except (ValueError, KeyError):
                pass
    return stats


def update_csv(results: dict[str, dict]) -> bool:
    """Blend WC results into Soccer-Stats.csv. Returns True if changed."""
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    changed = False
    updated = []
    for row in rows:
        team = row['Team']
        if team not in results:
            continue
        r = results[team]
        games     = r['games']
        actual_gf = r['gf'] / games
        actual_ga = r['ga'] / games
        prior_gf  = float(row['GF'])
        prior_ga  = float(row['GA'])
        w         = games / (games + PRIOR_GAMES)
        new_gf    = round(w * actual_gf + (1 - w) * prior_gf, 3)
        new_ga    = round(w * actual_ga + (1 - w) * prior_ga, 3)
        if new_gf != prior_gf or new_ga != prior_ga:
            row['GF']  = new_gf
            row['GA']  = new_ga
            row['wGF'] = round(new_gf / INTL_CONSTANT, 3)
            row['wGA'] = round(new_ga / INTL_CONSTANT, 3)
            changed = True
            updated.append(
                f'  {team}: {games} games, w={w:.0%}  '
                f'GF {prior_gf:.3f}→{new_gf:.3f}  GA {prior_ga:.3f}→{new_ga:.3f}'
            )

    if changed:
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f'[WC] Updated {len(updated)} teams in CSV:')
        for line in updated:
            print(line)
    else:
        print('[WC] CSV already up to date.')
    return changed


# ── Soccer model ──────────────────────────────────────────────────────────────

def soccer_prediction(home: dict, away: dict) -> tuple[float, float]:
    """Port of TypeScript scoreboard formula, neutral-site (no home advantage)."""
    wl_ratio_h = (home['wLeague'] / away['wLeague']) ** 2
    wl_ratio_a = (away['wLeague'] / home['wLeague']) ** 2
    home_xg = ((home['GF'] * away['wGA']) + (home['wGF'] * away['GA'])) / 2 * wl_ratio_h
    away_xg = ((away['GF'] * home['wGA']) + (away['wGF'] * home['GA'])) / 2 * wl_ratio_a
    return round(max(home_xg, 0.0), 2), round(max(away_xg, 0.0), 2)


def win_prob(home_xg: float, away_xg: float) -> float:
    """Simple logistic win probability from expected goal difference."""
    return round(1.0 / (1.0 + math.exp(-0.85 * (home_xg - away_xg))), 3)


# ── Firestore ─────────────────────────────────────────────────────────────────

def save_to_firestore(matches: list, stats: dict):
    """
    For each WC match:
      - If doc doesn't exist: create with prediction (+ actual if finished).
      - If doc exists and game just finished: update actual scores only.
    """
    if not SA_JSON_STR:
        print('[WC] FIREBASE_SERVICE_ACCOUNT_JESIMON4_SCOREBOARD not set — skipping Firestore.')
        return

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[WC] firebase-admin not installed — skipping Firestore.')
        return

    cred = credentials.Certificate(json.loads(SA_JSON_STR))
    app  = firebase_admin.initialize_app(cred)
    db   = fb_firestore.client()

    created = updated = skipped = 0

    for m in matches:
        match_id  = m.get('id')
        status    = m.get('status', '')
        home_fd   = m.get('homeTeam', {}).get('name', '')
        away_fd   = m.get('awayTeam', {}).get('name', '')
        home_csv  = FD_TO_CSV.get(home_fd, home_fd)
        away_csv  = FD_TO_CSV.get(away_fd, away_fd)
        game_date = m.get('utcDate', '')[:10]  # "2026-06-15"

        if home_csv not in stats or away_csv not in stats:
            skipped += 1
            continue

        home_s = stats[home_csv]
        away_s = stats[away_csv]
        home_xg, away_xg = soccer_prediction(home_s, away_s)
        wp = win_prob(home_xg, away_xg)

        # Actual scores (None if not finished)
        actual_home = actual_away = None
        if status == 'FINISHED':
            score = m.get('score', {})
            ft = score.get('fullTime', {})
            actual_home = ft.get('home')
            actual_away = ft.get('away')

        doc_id  = f'WC_{match_id}'
        doc_ref = db.collection('games').document(doc_id)
        existing = doc_ref.get()

        if existing.exists:
            # Only update if we now have actual scores that weren't there before
            if actual_home is not None and existing.to_dict().get('actualHomeScore') is None:
                doc_ref.update({
                    'actualHomeScore': int(actual_home),
                    'actualAwayScore': int(actual_away),
                })
                print(f'  [Updated] {away_csv} @ {home_csv}: {actual_away}-{actual_home}')
                updated += 1
        else:
            doc_ref.set({
                'sport':               'World Cup',
                'homeTeam':            home_csv,
                'awayTeam':            away_csv,
                'predictedHomeScore':  home_xg,
                'predictedAwayScore':  away_xg,
                'actualHomeScore':     int(actual_home) if actual_home is not None else None,
                'actualAwayScore':     int(actual_away) if actual_away is not None else None,
                'winProb':             wp,
                'gameDate':            game_date,
                'matchId':             match_id,
                'timestamp':           fb_firestore.SERVER_TIMESTAMP,
            })
            label = f'{actual_away}-{actual_home}' if actual_home is not None else 'upcoming'
            print(f'  [Saved] {away_csv} @ {home_csv} ({label})  pred {away_xg}-{home_xg}')
            created += 1

    firebase_admin.delete_app(app)
    print(f'[WC] Firestore: {created} created, {updated} score-updated, {skipped} skipped.')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        print('[WC] FOOTBALL_DATA_API_KEY not set — skipping.')
        sys.exit(0)

    # Fetch ALL matches (finished + upcoming) in one call
    print('[WC] Fetching all WC 2026 matches...')
    data    = _get('/competitions/WC/matches', {'season': 2026})
    matches = data.get('matches', [])
    print(f'[WC] {len(matches)} total matches.')

    # Aggregate finished results for CSV update
    finished_results: dict[str, dict] = {}
    for m in matches:
        if m.get('status') != 'FINISHED':
            continue
        score = m.get('score', {}).get('fullTime', {})
        hg = score.get('home')
        ag = score.get('away')
        if hg is None or ag is None:
            continue
        home_csv = FD_TO_CSV.get(m['homeTeam']['name'], m['homeTeam']['name'])
        away_csv = FD_TO_CSV.get(m['awayTeam']['name'], m['awayTeam']['name'])
        for team, gf, ga in [(home_csv, hg, ag), (away_csv, ag, hg)]:
            finished_results.setdefault(team, {'gf': 0, 'ga': 0, 'games': 0})
            finished_results[team]['gf']    += gf
            finished_results[team]['ga']    += ga
            finished_results[team]['games'] += 1

    # Step 1: update CSV with blended stats
    if finished_results:
        update_csv(finished_results)
    else:
        print('[WC] No finished matches yet — CSV unchanged.')

    # Step 2: load the freshly-updated stats, then save predictions to Firestore
    stats = load_stats()
    save_to_firestore(matches, stats)


if __name__ == '__main__':
    main()
