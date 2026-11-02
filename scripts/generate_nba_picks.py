"""
Generate NBA game picks and write nba-picks.json.
Also saves predictions to Firestore (Results page).

Uses NBA-Stats.csv (team ratings) and fetches the schedule from the
ESPN NBA scoreboard API (no key required).

Simulation mirrors scoreboard.component.ts NBA case:
  Poss      = homeTeam.Tempo * awayTeam.adjT
  HomeOEff  = Off*.17 + oLastThree*.18 + oHome*.15
  AwayDEff  = Def*.17 + dLastThree*.18 + dAway*.15
  ...
  homeScore = floor(((HomeOEff * awayTeam.adjD) + (AwayDEff * homeTeam.adjO)) * Poss + 1.1)
  awayScore = floor(((AwayOEff * homeTeam.adjD) + (HomeDEff * awayTeam.adjO)) * Poss - 1.1)

Output: src/assets/nba-picks.json
"""

import csv
import json
import math
import os
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_PATH = os.path.join(ASSETS, 'NBA-Stats.csv')
OUTPUT     = os.path.join(ASSETS, 'nba-picks.json')
SA_JSON    = os.environ.get('FIREBASE_SERVICE_ACCOUNT', '')
ET         = ZoneInfo('America/New_York')

WIN_PROB_K   = 0.08   # logistic scaling; a 10-pt diff → ~73% win prob
HOME_ADV     = 1.1    # points, matches Angular constant

# ESPN abbreviation → our NBA-Stats.csv team name
ABBREV_TO_NAME = {
    'ATL':  'Atlanta Hawks',
    'BOS':  'Boston Celtics',
    'BKN':  'Brooklyn Nets',
    'CHA':  'Charlotte Hornets',
    'CHI':  'Chicago Bulls',
    'CLE':  'Cleveland Cavaliers',
    'DAL':  'Dallas Mavericks',
    'DEN':  'Denver Nuggets',
    'DET':  'Detroit Pistons',
    'GS':   'Golden State Warriors',   # ESPN uses GS, not GSW
    'GSW':  'Golden State Warriors',
    'HOU':  'Houston Rockets',
    'IND':  'Indiana Pacers',
    'LAC':  'Los Angeles Clippers',    # CSV uses full name
    'LAL':  'Los Angeles Lakers',
    'MEM':  'Memphis Grizzlies',
    'MIA':  'Miami Heat',
    'MIL':  'Milwaukee Bucks',
    'MIN':  'Minnesota Timberwolves',
    'NO':   'New Orleans Pelicans',    # ESPN uses NO
    'NOP':  'New Orleans Pelicans',
    'NY':   'New York Knicks',         # ESPN uses NY
    'NYK':  'New York Knicks',
    'OKC':  'Oklahoma City Thunder',
    'ORL':  'Orlando Magic',
    'PHI':  'Philadelphia 76ers',
    'PHX':  'Phoenix Suns',
    'POR':  'Portland Trail Blazers',
    'SAC':  'Sacramento Kings',
    'SA':   'San Antonio Spurs',       # ESPN uses SA
    'SAS':  'San Antonio Spurs',
    'TOR':  'Toronto Raptors',
    'UTA':  'Utah Jazz',
    'UTAH': 'Utah Jazz',               # ESPN uses UTAH
    'WAS':  'Washington Wizards',
    'WSH':  'Washington Wizards',      # ESPN uses WSH
}


def load_team_stats() -> dict:
    stats = {}
    if not os.path.exists(STATS_PATH):
        print('[NBA Picks] NBA-Stats.csv not found.')
        return stats
    with open(STATS_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                team = row['Team'].strip()
                stats[team] = {
                    'Off':        float(row['Off']),
                    'oLastThree': float(row['oLastThree']),
                    'oHome':      float(row['oHome']),
                    'oAway':      float(row['oAway']),
                    'adjO':       float(row['adjO']),
                    'Def':        float(row['Def']),
                    'dLastThree': float(row['dLastThree']),
                    'dHome':      float(row['dHome']),
                    'dAway':      float(row['dAway']),
                    'adjD':       float(row['adjD']),
                    'Tempo':      float(row['Tempo']),
                    'adjT':       float(row['adjT']),
                }
            except (ValueError, KeyError):
                pass
    print(f'[NBA Picks] Loaded stats for {len(stats)} teams.')
    return stats


def simulate(home: dict, away: dict) -> tuple[float, float]:
    """Mirror the Angular NBA simulation formula."""
    poss      = home['Tempo'] * away['adjT']
    home_oeff = home['Off'] * .17 + home['oLastThree'] * .18 + home['oHome'] * .15
    away_deff = away['Def'] * .17 + away['dLastThree'] * .18 + away['dAway'] * .15
    away_oeff = away['Off'] * .17 + away['oLastThree'] * .18 + away['oAway'] * .15
    home_deff = home['Def'] * .17 + home['dLastThree'] * .18 + home['dHome'] * .15

    home_score = math.floor(((home_oeff * away['adjD']) + (away_deff * home['adjO'])) * poss + HOME_ADV)
    away_score = math.floor(((away_oeff * home['adjD']) + (home_deff * away['adjO'])) * poss - HOME_ADV)
    return float(home_score), float(away_score)


def win_prob(diff: float) -> float:
    return round(1 / (1 + math.exp(-WIN_PROB_K * diff)), 3)


def confidence_label(edge: float) -> str:
    if edge >= 0.18: return 'Elite'
    if edge >= 0.10: return 'Strong'
    if edge >= 0.05: return 'Lean'
    return ''


def fetch_schedule(dates: list) -> list:
    """Fetch NBA games for the given ET date strings using ESPN API."""
    games = []
    seen  = set()
    for date_str in dates:
        date_compact = date_str.replace('-', '')
        url = f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_compact}'
        try:
            resp = requests.get(url, timeout=15,
                                headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                print(f'[NBA Picks] ESPN schedule {date_str}: HTTP {resp.status_code}')
                continue
            for event in resp.json().get('events', []):
                eid = event.get('id')
                if eid in seen:
                    continue
                seen.add(eid)
                games.append(event)
            print(f'[NBA Picks] ESPN {date_str}: {len(games)} games so far')
        except Exception as exc:
            print(f'[NBA Picks] ESPN {date_str} error: {exc}')
    return games


def parse_event(event: dict) -> dict | None:
    """Extract relevant fields from an ESPN event."""
    competition = (event.get('competitions') or [{}])[0]
    competitors = competition.get('competitors', [])
    if len(competitors) < 2:
        return None

    home_comp = next((c for c in competitors if c.get('homeAway') == 'home'), None)
    away_comp = next((c for c in competitors if c.get('homeAway') == 'away'), None)
    if not home_comp or not away_comp:
        return None

    home_abbrev = (home_comp.get('team') or {}).get('abbreviation', '')
    away_abbrev = (away_comp.get('team') or {}).get('abbreviation', '')
    home_name   = ABBREV_TO_NAME.get(home_abbrev)
    away_name   = ABBREV_TO_NAME.get(away_abbrev)
    if not home_name or not away_name:
        print(f'[NBA Picks] Unknown abbrev: {home_abbrev} / {away_abbrev}')
        return None

    start_utc = event.get('date', '')   # ISO UTC

    status      = (competition.get('status') or {}).get('type', {})
    is_final    = status.get('completed', False)
    home_score  = None
    away_score  = None
    if is_final:
        try:
            home_score = int(home_comp.get('score', 0))
            away_score = int(away_comp.get('score', 0))
        except (TypeError, ValueError):
            pass

    # Extract Vegas spread from ESPN odds (negative ESPN spread = home favorite)
    odds_list = competition.get('odds') or []
    vegas_spread = None
    if odds_list:
        raw = odds_list[0].get('spread')
        if raw is not None:
            try:
                vegas_spread = round(-float(raw), 1)
            except (ValueError, TypeError):
                pass

    return {
        'gameId':     event.get('id'),
        'homeTeam':   home_name,
        'awayTeam':   away_name,
        'startUTC':   start_utc,
        'isFinal':    is_final,
        'homeActual': home_score,
        'awayActual': away_score,
        'vegasSpread': vegas_spread,
    }


def save_to_firestore(picks_data: list):
    if not SA_JSON:
        print('[NBA Picks] FIREBASE_SERVICE_ACCOUNT not set — skipping Firestore.')
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[NBA Picks] firebase-admin not installed — skipping Firestore.')
        return
    try:
        cred = credentials.Certificate(json.loads(SA_JSON))
        app  = firebase_admin.initialize_app(cred, name='nba_picks')
        db   = fb_firestore.client(app)

        now_utc   = datetime.now(timezone.utc)
        created = updated = skipped = 0

        for p in picks_data:
            home     = p['homeTeam']
            away     = p['awayTeam']
            gt       = p.get('gameTime', '')
            date_str = gt[:10] if gt else ''
            h_norm   = home.replace(' ', '_').replace("'", '')
            a_norm   = away.replace(' ', '_').replace("'", '')
            doc_id   = f'nba_{h_norm}_{a_norm}_{date_str}'
            doc_ref  = db.collection('games').document(doc_id)
            existing = doc_ref.get()

            actual_home = p.get('actualHomeScore')
            actual_away = p.get('actualAwayScore')

            # Lock predictions within 24 h of tip-off
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
                    'sport':              'NBA',
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
        print(f'[NBA Picks] Firestore: {created} created, {updated} updated, {skipped} skipped.')
    except Exception as exc:
        print(f'[NBA Picks] Firestore error: {exc}')


def main():
    stats = load_team_stats()
    if not stats:
        print('[NBA Picks] No stats — aborting.')
        return

    now    = datetime.now(timezone.utc)
    now_et = now.astimezone(ET)
    # Fetch yesterday + today + next 2 days so completed games get actual scores backfilled
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
            print(f'[NBA Picks] Missing stats for {home_name} or {away_name} — skipping.')
            skipped += 1
            continue

        h_score, a_score = simulate(h_stats, a_stats)
        diff  = h_score - a_score
        wp    = win_prob(diff)
        if wp >= 0.5:
            pick_team, pick_wp = home_name, wp
        else:
            pick_team, pick_wp = away_name, round(1 - wp, 3)
        edge  = pick_wp - 0.5

        # Spread edge vs Vegas (positive = model likes home more than Vegas does)
        vegas_home  = parsed.get('vegasSpread')
        spread_edge = round((h_score - a_score) - vegas_home, 1) if vegas_home is not None else None
        if spread_edge is not None:
            abs_se = abs(spread_edge)
            label  = 'Elite' if abs_se >= 10 else ('Strong' if abs_se >= 6 else ('Lean' if abs_se >= 3 else ''))
        else:
            label = confidence_label(edge)

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
            'vegasSpread':        vegas_home,
            'spreadEdge':         spread_edge,
            'gameTime':           parsed['startUTC'],
        }
        firestore_data.append(entry)

        game_started = parsed['startUTC'] and datetime.fromisoformat(
            parsed['startUTC'].replace('Z', '+00:00')) <= now

        if not game_started and label:
            picks.append(entry)

    picks.sort(key=lambda p: abs(p.get('spreadEdge') or 0), reverse=True)
    for i, p in enumerate(picks):
        p['rank'] = i + 1

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)
    print(f'[NBA Picks] Wrote {len(picks)} picks -> {OUTPUT}')

    save_to_firestore(firestore_data)


if __name__ == '__main__':
    main()
