"""
Fetch European league and MLS match data from football-data.org and:
  1. Update team GF/GA stats in Soccer-Stats.csv (blended with pre-season baseline)
  2. Generate soccer-today.json with upcoming predictions + recent results
  3. Save predictions + actual scores to Firestore for Results tab tracking

Leagues: Premier League (PL), La Liga (PD), Serie A (SA),
         Bundesliga (BL1), Ligue 1 (FL1), MLS (MLS)

Requires:
  FOOTBALL_DATA_API_KEY                          — football-data.org API token
  FIREBASE_SERVICE_ACCOUNT_JESIMON4_SCOREBOARD   — Firebase service account JSON string

Blending: weight_actual = games / (games + PRIOR_GAMES)
  PRIOR_GAMES = 20  →  pre-season stats treated as 20 games of historical data.
  At 10 games played: 33% current season / 67% prior.
  At 20 games played: 50/50.
"""

import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API_KEY     = os.environ.get('FOOTBALL_DATA_API_KEY', '')
SA_JSON_STR = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JESIMON4_SCOREBOARD', '')
BASE        = 'https://api.football-data.org/v4'

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
CSV_PATH   = os.path.join(ASSETS, 'Soccer-Stats.csv')
TODAY_PATH = os.path.join(ASSETS, 'soccer-today.json')

PRIOR_GAMES   = 20     # pre-season data weighted as 20 games
CLUB_CONSTANT = 1.362  # default wGF = GF / CLUB_CONSTANT for new club teams

# For european leagues, start year of the season (e.g. 2026 for 2026-27)
EURO_SEASON = 2026
# MLS runs on a calendar year
MLS_SEASON  = 2025

# football-data.org competition code → metadata
# MLS competition code on football-data.org is 'MLS' (free-tier availability may vary)
LEAGUES = {
    'PL':  {'name': 'Premier League', 'season': EURO_SEASON, 'prefix': 'EPL', 'wLeague': 90.6},
    'PD':  {'name': 'La Liga',        'season': EURO_SEASON, 'prefix': 'LAL', 'wLeague': 84.8},
    'SA':  {'name': 'Serie A',        'season': EURO_SEASON, 'prefix': 'SA',  'wLeague': 84.8},
    'BL1': {'name': 'Bundesliga',     'season': EURO_SEASON, 'prefix': 'BL',  'wLeague': 84.2},
    'FL1': {'name': 'Ligue 1',        'season': EURO_SEASON, 'prefix': 'L1',  'wLeague': 84.3},
    'MLS': {'name': 'MLS',            'season': MLS_SEASON,  'prefix': 'MLS', 'wLeague': 72.0},
}

# Map football-data.org team names → Soccer-Stats.csv team names
FD_TO_CSV: dict[str, str] = {
    # ── Premier League ────────────────────────────────────────────────────────
    'Arsenal':                       'Arsenal',
    'Aston Villa':                   'Aston Villa',
    'Bournemouth':                   'Bournemouth',
    'Brentford':                     'Brentford',
    'Brighton & Hove Albion':        'Brighton',
    'Brighton':                      'Brighton',
    'Burnley':                       'Burnley',
    'Chelsea':                       'Chelsea',
    'Crystal Palace':                'Crystal Palace',
    'Everton':                       'Everton',
    'Fulham':                        'Fulham',
    'Ipswich Town':                  'Ipswich Town',
    'Leeds United':                  'Leeds Utd',
    'Leicester City':                'Leicester City',
    'Liverpool':                     'Liverpool',
    'Luton Town':                    'Luton Town',
    'Manchester City':               'Manchester City',
    'Manchester United':             'Manchester Utd',
    'Newcastle United':              'Newcastle Utd',
    'Nottingham Forest':             'Nottm Forest',
    'Sheffield United':              'Sheffield Utd',
    'Southampton':                   'Southampton',
    'Sunderland':                    'Sunderland',
    'Tottenham Hotspur':             'Tottenham',
    'West Ham United':               'West Ham Utd',
    'Wolverhampton Wanderers':       'Wolverhampton',
    # ── La Liga ───────────────────────────────────────────────────────────────
    'Real Madrid CF':                'Real Madrid',
    'Real Madrid':                   'Real Madrid',
    'Athletic Club':                 'Athletic Bilbao',
    'Athletic Bilbao':               'Athletic Bilbao',
    'Villarreal CF':                 'Villarreal',
    'Villarreal':                    'Villarreal',
    'FC Barcelona':                  'FC Barcelona',
    'RCD Espanyol de Barcelona':     'Espanyol',
    'Espanyol':                      'Espanyol',
    'Getafe CF':                     'Getafe',
    'Getafe':                        'Getafe',
    'Elche CF':                      'Elche',
    'Real Betis Balompié':           'Real Betis',
    'Real Betis':                    'Real Betis',
    'Valencia CF':                   'Valencia',
    'Valencia':                      'Valencia',
    'Rayo Vallecano de Madrid':      'Rayo Vallecano',
    'Rayo Vallecano':                'Rayo Vallecano',
    'Deportivo Alavés':              'Alaves',
    'Alaves':                        'Alaves',
    'Sevilla FC':                    'Sevilla FC',
    'CA Osasuna':                    'Osasuna',
    'Osasuna':                       'Osasuna',
    'RC Celta de Vigo':              'Celta Vigo',
    'Celta Vigo':                    'Celta Vigo',
    'Real Oviedo':                   'Real Oviedo',
    'Club Atlético de Madrid':       'Atletico Madrid',
    'Atletico Madrid':               'Atletico Madrid',
    'Real Sociedad de Fútbol':       'Real Sociedad',
    'Real Sociedad':                 'Real Sociedad',
    'RCD Mallorca':                  'Mallorca',
    'Mallorca':                      'Mallorca',
    'Levante UD':                    'Levante',
    'Girona FC':                     'Girona',
    'Girona':                        'Girona',
    'UD Las Palmas':                 'Las Palmas',
    'Real Valladolid CF':            'Valladolid',
    # ── Serie A ───────────────────────────────────────────────────────────────
    'Juventus FC':                   'Juventus',
    'Juventus':                      'Juventus',
    'SSC Napoli':                    'Napoli',
    'Napoli':                        'Napoli',
    'US Cremonese':                  'Cremonese',
    'AS Roma':                       'AS Roma',
    'Udinese Calcio':                'Udinese',
    'Udinese':                       'Udinese',
    'FC Internazionale Milano':      'Inter Milan',
    'Inter Milan':                   'Inter Milan',
    'SS Lazio':                      'Lazio',
    'AC Milan':                      'AC Milan',
    'Como 1907':                     'Como',
    'Como':                          'Como',
    'Bologna FC 1909':               'Bologna',
    'Bologna':                       'Bologna',
    'Atalanta BC':                   'Atalanta',
    'Atalanta':                      'Atalanta',
    'ACF Fiorentina':                'Fiorentina',
    'Fiorentina':                    'Fiorentina',
    'Cagliari Calcio':               'Cagliari',
    'Cagliari':                      'Cagliari',
    'AC Pisa 1909':                  'Pisa',
    'Genoa CFC':                     'Genoa',
    'Parma Calcio 1913':             'Parma',
    'US Lecce':                      'Lecce',
    'Hellas Verona FC':              'Hellas Verona',
    'Torino FC':                     'Torino',
    'US Sassuolo Calcio':            'Sassuolo',
    'Empoli FC':                     'Empoli',
    'Venezia FC':                    'Venezia',
    'AC Monza':                      'Monza',
    'Monza':                         'Monza',
    # ── Bundesliga ────────────────────────────────────────────────────────────
    'FC Bayern München':             'Bayern Munich',
    'Bayern Munich':                 'Bayern Munich',
    'Eintracht Frankfurt':           'E. Frankfurt',
    'E. Frankfurt':                  'E. Frankfurt',
    '1. FC Köln':                    'FC Koln',
    'FC Koln':                       'FC Koln',
    'Borussia Dortmund':             'Dortmund',
    'Dortmund':                      'Dortmund',
    'FC St. Pauli':                  'Sankt Pauli',
    'Sankt Pauli':                   'Sankt Pauli',
    'VfL Wolfsburg':                 'Wolfsburg',
    'FC Augsburg':                   'FC Augsburg',
    'VfB Stuttgart':                 'Stuttgart',
    'TSG 1899 Hoffenheim':           'Hoffenheim',
    'Hoffenheim':                    'Hoffenheim',
    '1. FC Union Berlin':            'Union Berlin',
    'Union Berlin':                  'Union Berlin',
    'RB Leipzig':                    'RB Leipzig',
    'Bayer 04 Leverkusen':           'Leverkusen',
    'Leverkusen':                    'Leverkusen',
    '1. FSV Mainz 05':               'FSV Mainz',
    'FSV Mainz':                     'FSV Mainz',
    'Borussia Mönchengladbach':      'Monchengladbach',
    'Monchengladbach':               'Monchengladbach',
    'Hamburger SV':                  'Hamburger SV',
    'SV Werder Bremen':              'Werder Bremen',
    'Werder Bremen':                 'Werder Bremen',
    '1. FC Heidenheim 1846':         'Heidenheim',
    'Heidenheim':                    'Heidenheim',
    'SC Freiburg':                   'Freiburg',
    'Freiburg':                      'Freiburg',
    'VfL Bochum 1848':               'Bochum',
    'Bochum':                        'Bochum',
    'Fortuna Düsseldorf':            'Fortuna Dusseldorf',
    'Holstein Kiel':                 'Holstein Kiel',
    # ── Ligue 1 ───────────────────────────────────────────────────────────────
    'Paris Saint-Germain FC':        'Paris SG',
    'Paris SG':                      'Paris SG',
    'Olympique Lyonnais':            'Lyon',
    'Lyon':                          'Lyon',
    'LOSC Lille':                    'Lille',
    'Lille':                         'Lille',
    'AS Monaco FC':                  'Monaco',
    'Monaco':                        'Monaco',
    'RC Lens':                       'Lens',
    'RC Strasbourg Alsace':          'Strasbourg',
    'Strasbourg':                    'Strasbourg',
    'Toulouse FC':                   'Toulouse',
    'Angers SCO':                    'Angers',
    'Stade Rennais FC 1901':         'Rennes',
    'Rennes':                        'Rennes',
    'Olympique de Marseille':        'Marseille',
    'Marseille':                     'Marseille',
    'Le Havre AC':                   'Le Havre',
    'Havre AC':                      'Le Havre',
    'OGC Nice':                      'Nice',
    'Nice':                          'Nice',
    'FC Nantes':                     'Nantes',
    'AJ Auxerre':                    'Auxerre',
    'Auxerre':                       'Auxerre',
    'FC Lorient':                    'Lorient',
    'Paris FC':                      'Paris FC',
    'Stade Brestois 29':             'Brest',
    'Brest':                         'Brest',
    'FC Metz':                       'Metz',
    'AS Saint-Étienne':              'Saint-Etienne',
    'Montpellier HSC':               'Montpellier',
    # ── MLS ───────────────────────────────────────────────────────────────────
    'Atlanta United FC':             'Atlanta United',
    'Charlotte FC':                  'Charlotte FC',
    'Chicago Fire FC':               'Chicago Fire',
    'FC Cincinnati':                 'FC Cincinnati',
    'Columbus Crew':                 'Columbus Crew',
    'Columbus Crew SC':              'Columbus Crew',
    'DC United':                     'D.C. United',
    'D.C. United':                   'D.C. United',
    'Inter Miami CF':                'Inter Miami',
    'CF Montréal':                   'CF Montréal',
    'Nashville SC':                  'Nashville SC',
    'New England Revolution':        'New England Revolution',
    'New York City FC':              'New York City FC',
    'New York Red Bulls':            'New York Red Bulls',
    'Orlando City SC':               'Orlando City SC',
    'Philadelphia Union':            'Philadelphia Union',
    'Toronto FC':                    'Toronto FC',
    'Austin FC':                     'Austin FC',
    'Colorado Rapids':               'Colorado Rapids',
    'FC Dallas':                     'FC Dallas',
    'Houston Dynamo FC':             'Houston Dynamo',
    'Houston Dynamo':                'Houston Dynamo',
    'LA Galaxy':                     'LA Galaxy',
    'Los Angeles FC':                'Los Angeles FC',
    'Minnesota United FC':           'Minnesota United',
    'Portland Timbers':              'Portland Timbers',
    'Real Salt Lake':                'Real Salt Lake',
    'San Diego FC':                  'San Diego FC',
    'San Jose Earthquakes':          'San Jose Earthquakes',
    'Seattle Sounders FC':           'Seattle Sounders',
    'Sporting Kansas City':          'Sporting KC',
    'St. Louis City SC':             'St. Louis City SC',
    'Vancouver Whitecaps FC':        'Vancouver Whitecaps',
    'Vancouver Whitecaps':           'Vancouver Whitecaps',
}

# Maps league name → the Teams CSV file used by the Angular dropdown
LEAGUE_TO_TEAMS_CSV: dict[str, str] = {
    'Premier League': 'Premier League-Teams.csv',
    'La Liga':        'La Liga-Teams.csv',
    'Serie A':        'Serie A-Teams.csv',
    'Bundesliga':     'Bundesliga-Teams.csv',
    'Ligue 1':        'Ligue 1-Teams.csv',
    # MLS omitted — free-tier API availability is inconsistent
}

ACTIVE_STATUSES = {'SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED', 'LIVE'}


# ── API ──────────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> dict:
    resp = requests.get(
        f'{BASE}{endpoint}',
        headers={'X-Auth-Token': API_KEY},
        params=params or {},
        timeout=30,
    )
    if resp.status_code == 429:
        print('  [rate-limit] waiting 61s...')
        time.sleep(61)
        resp = requests.get(f'{BASE}{endpoint}',
                            headers={'X-Auth-Token': API_KEY},
                            params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_league(code: str, season: int) -> list:
    """Return all matches for a competition/season, or [] on error."""
    try:
        data    = _get(f'/competitions/{code}/matches', {'season': season})
        matches = data.get('matches', [])
        print(f'[{code}] {len(matches)} matches (season {season}).')
        return matches
    except requests.HTTPError as exc:
        print(f'[{code}] HTTP {exc.response.status_code} — skipping.')
        return []
    except Exception as exc:
        print(f'[{code}] Error: {exc} — skipping.')
        return []


# ── CSV helpers ───────────────────────────────────────────────────────────────

def load_stats() -> dict[str, dict]:
    stats = {}
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                stats[row['Team']] = {
                    'GF':      float(row['GF']),
                    'GA':      float(row['GA']),
                    'wGF':     float(row['wGF']) if row.get('wGF', '') not in ('#REF!', '', None) else 0.0,
                    'wGA':     float(row['wGA']) if row.get('wGA', '') not in ('#REF!', '', None) else 0.0,
                    'wLeague': float(row['wLeague']),
                    'HomeAdv': float(row['HomeAdv']),
                }
            except (ValueError, KeyError):
                pass
    return stats


def update_csv(league_results: dict[str, dict[str, dict]], league_wratings: dict[str, float]) -> bool:
    """
    Blend season results into Soccer-Stats.csv.
    league_results: {league_name: {csv_team_name: {gf, ga, games}}}
    Returns True if any row changed.
    """
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        rows     = list(csv.DictReader(f))
    fieldnames   = list(rows[0].keys())
    existing     = {row['Team'] for row in rows}

    # Flatten to {team: (result_dict, wLeague)}
    all_results: dict[str, tuple[dict, float]] = {}
    for league_name, team_map in league_results.items():
        wl = league_wratings.get(league_name, 75.0)
        for team, r in team_map.items():
            all_results[team] = (r, wl)

    changed   = False
    new_rows  = []
    log_lines = []

    # Update existing rows
    for row in rows:
        team = row['Team']
        if team not in all_results:
            continue
        r, _wl = all_results[team]
        games     = r['games']
        actual_gf = r['gf'] / games
        actual_ga = r['ga'] / games
        prior_gf  = float(row['GF'])
        prior_ga  = float(row['GA'])
        w         = games / (games + PRIOR_GAMES)
        new_gf    = round(w * actual_gf + (1 - w) * prior_gf, 3)
        new_ga    = round(w * actual_ga + (1 - w) * prior_ga, 3)

        if new_gf == prior_gf and new_ga == prior_ga:
            continue

        # Preserve each team's existing wGF/GF ratio; fall back to CLUB_CONSTANT
        prior_wgf = float(row['wGF']) if row.get('wGF', '') not in ('#REF!', '', None) else 0.0
        prior_wga = float(row['wGA']) if row.get('wGA', '') not in ('#REF!', '', None) else 0.0
        gf_ratio  = (prior_wgf / prior_gf) if prior_gf > 0 and prior_wgf > 0 else (1 / CLUB_CONSTANT)
        ga_ratio  = (prior_wga / prior_ga) if prior_ga > 0 and prior_wga > 0 else (1 / CLUB_CONSTANT)

        row['GF']  = new_gf
        row['GA']  = new_ga
        row['wGF'] = round(new_gf * gf_ratio, 3)
        row['wGA'] = round(new_ga * ga_ratio, 3)
        changed = True
        log_lines.append(
            f'  {team}: {games}g w={w:.0%}  GF {prior_gf:.3f}→{new_gf:.3f}  GA {prior_ga:.3f}→{new_ga:.3f}'
        )

    # Add brand-new teams (promoted clubs, etc.)
    for team, (r, wl) in all_results.items():
        if team in existing:
            continue
        games = r['games']
        gf    = round(r['gf'] / games, 3)
        ga    = round(r['ga'] / games, 3)
        new_rows.append({
            'Team': team, 'GF': gf, 'GA': ga,
            'wGF': round(gf / CLUB_CONSTANT, 3),
            'wGA': round(ga / CLUB_CONSTANT, 3),
            'wLeague': wl, 'HomeAdv': 0.1,
        })
        print(f'  [New team] {team}: GF={gf}, GA={ga}, wLeague={wl}')
        existing.add(team)
        changed = True

    if changed:
        all_rows = rows + new_rows
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        if log_lines:
            print(f'[Soccer] Updated {len(log_lines)} teams:')
            for line in log_lines:
                print(line)
    else:
        print('[Soccer] CSV already up to date.')
    return changed


def update_teams_csv(league_name: str, teams: list[str]):
    """
    Rewrite the league's dropdown Teams CSV with the current season's team list.
    Teams are derived from match data (all fixtures, not just finished games),
    so promoted/relegated sides stay current without manual edits.
    """
    csv_file = LEAGUE_TO_TEAMS_CSV.get(league_name)
    if not csv_file:
        return
    path = os.path.join(ASSETS, csv_file)
    sorted_teams = sorted(set(t for t in teams if t))
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(league_name + '\n')
        for team in sorted_teams:
            f.write(team + '\n')
    print(f'[{league_name}] Teams CSV updated: {len(sorted_teams)} teams.')


# ── Soccer model ─────────────────────────────────────────────────────────────

def soccer_prediction(home: dict, away: dict) -> tuple[float, float]:
    home_adv = home.get('HomeAdv', 0.1)
    wl_h     = (home['wLeague'] / away['wLeague']) ** 2
    wl_a     = (away['wLeague'] / home['wLeague']) ** 2
    h_xg     = ((home['GF'] * away['wGA']) + (home['wGF'] * away['GA'])) / 2 * wl_h * (1 + home_adv)
    a_xg     = ((away['GF'] * home['wGA']) + (away['wGF'] * home['GA'])) / 2 * wl_a * (1 - home_adv)
    return round(max(h_xg, 0.0), 2), round(max(a_xg, 0.0), 2)


def win_prob(home_xg: float, away_xg: float) -> float:
    return round(1.0 / (1.0 + math.exp(-0.85 * (home_xg - away_xg))), 3)


# ── Today JSON ───────────────────────────────────────────────────────────────

def generate_today_json(all_matches: dict[str, list], stats: dict):
    now       = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')
    window    = now + timedelta(days=7)   # show matches up to 7 days out

    upcoming = []
    results  = []

    for code, matches in all_matches.items():
        league_name = LEAGUES[code]['name']
        for m in matches:
            status   = m.get('status', '')
            home_fd  = m.get('homeTeam', {}).get('name', '')
            away_fd  = m.get('awayTeam', {}).get('name', '')
            home_csv = FD_TO_CSV.get(home_fd, home_fd)
            away_csv = FD_TO_CSV.get(away_fd, away_fd)

            if home_csv not in stats or away_csv not in stats:
                continue

            game_time = m.get('utcDate', '')
            game_date = game_time[:10]
            matchday  = m.get('matchday')
            round_lbl = f'Matchday {matchday}' if matchday else 'Match'

            h_xg, a_xg = soccer_prediction(stats[home_csv], stats[away_csv])
            wp          = win_prob(h_xg, a_xg)

            entry = {
                'matchId':            m.get('id'),
                'league':             league_name,
                'round':              round_lbl,
                'homeTeam':           home_csv,
                'awayTeam':           away_csv,
                'predictedHomeScore': h_xg,
                'predictedAwayScore': a_xg,
                'homeWinProb':        wp,
                'gameDate':           game_date,
                'gameTime':           game_time,
                'status':             status,
                'actualHomeScore':    None,
                'actualAwayScore':    None,
            }

            if status == 'FINISHED':
                # Only include results from the last 14 days
                try:
                    match_dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                    if (now - match_dt).days <= 14:
                        ft = m.get('score', {}).get('fullTime', {})
                        entry['actualHomeScore'] = ft.get('home')
                        entry['actualAwayScore'] = ft.get('away')
                        results.append(entry)
                except ValueError:
                    pass
            elif status in ACTIVE_STATUSES:
                try:
                    match_dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                    if match_dt <= window:
                        upcoming.append(entry)
                except ValueError:
                    upcoming.append(entry)

    upcoming.sort(key=lambda x: x['gameTime'])
    results.sort(key=lambda x: x['gameTime'], reverse=True)

    output = {
        'generated':     now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'today':         today_str,
        'upcoming':      upcoming[:24],
        'recentResults': results[:20],
    }

    with open(TODAY_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    print(f'[Soccer] soccer-today.json: {len(upcoming[:24])} upcoming, {len(results[:20])} results.')


# ── Firestore ─────────────────────────────────────────────────────────────────

def save_to_firestore(all_matches: dict[str, list], stats: dict):
    if not SA_JSON_STR:
        print('[Soccer] No Firebase credentials — skipping Firestore.')
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
    except ImportError:
        print('[Soccer] firebase-admin not installed — skipping Firestore.')
        return

    cred = credentials.Certificate(json.loads(SA_JSON_STR))
    app  = firebase_admin.initialize_app(cred)
    db   = fb_firestore.client()

    now          = datetime.now(timezone.utc)
    look_back    = now - timedelta(days=30)
    look_forward = now + timedelta(days=3)

    created = updated = skipped = 0

    for code, matches in all_matches.items():
        prefix      = LEAGUES[code]['prefix']
        league_name = LEAGUES[code]['name']

        for m in matches:
            status   = m.get('status', '')
            game_time = m.get('utcDate', '')
            try:
                match_dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
            except ValueError:
                skipped += 1
                continue

            # Only track games within a rolling window
            if match_dt < look_back or match_dt > look_forward:
                skipped += 1
                continue

            home_fd  = m.get('homeTeam', {}).get('name', '')
            away_fd  = m.get('awayTeam', {}).get('name', '')
            home_csv = FD_TO_CSV.get(home_fd, home_fd)
            away_csv = FD_TO_CSV.get(away_fd, away_fd)

            if home_csv not in stats or away_csv not in stats:
                skipped += 1
                continue

            h_xg, a_xg = soccer_prediction(stats[home_csv], stats[away_csv])
            wp          = win_prob(h_xg, a_xg)

            actual_home = actual_away = None
            if status == 'FINISHED':
                ft          = m.get('score', {}).get('fullTime', {})
                actual_home = ft.get('home')
                actual_away = ft.get('away')

            doc_id   = f'{prefix}_{m.get("id")}'
            doc_ref  = db.collection('games').document(doc_id)
            existing = doc_ref.get()

            if existing.exists:
                if actual_home is not None and existing.to_dict().get('actualHomeScore') is None:
                    doc_ref.update({
                        'actualHomeScore': int(actual_home),
                        'actualAwayScore': int(actual_away),
                    })
                    print(f'  [Updated] {away_csv} @ {home_csv}: {actual_away}-{actual_home}')
                    updated += 1
            else:
                if status not in ('FINISHED', 'SCHEDULED', 'TIMED', *ACTIVE_STATUSES):
                    skipped += 1
                    continue
                doc_ref.set({
                    'sport':              league_name,
                    'homeTeam':           home_csv,
                    'awayTeam':           away_csv,
                    'predictedHomeScore': h_xg,
                    'predictedAwayScore': a_xg,
                    'actualHomeScore':    int(actual_home) if actual_home is not None else None,
                    'actualAwayScore':    int(actual_away) if actual_away is not None else None,
                    'winProb':            wp,
                    'gameDate':           game_time[:10],
                    'matchId':            m.get('id'),
                    'timestamp':          fb_firestore.SERVER_TIMESTAMP,
                })
                label = f'{actual_away}-{actual_home}' if actual_home is not None else 'upcoming'
                print(f'  [Saved] {away_csv} @ {home_csv} ({league_name}, {label})')
                created += 1

    firebase_admin.delete_app(app)
    print(f'[Soccer] Firestore: {created} created, {updated} score-updated, {skipped} skipped.')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        print('[Soccer] FOOTBALL_DATA_API_KEY not set — exiting.')
        sys.exit(0)

    all_matches:    dict[str, list]             = {}
    league_results: dict[str, dict[str, dict]] = {}
    league_wratings: dict[str, float]          = {}

    for code, meta in LEAGUES.items():
        matches = fetch_league(code, meta['season'])
        if not matches:
            continue

        all_matches[code] = matches
        league_name       = meta['name']
        w_league          = meta['wLeague']
        league_wratings[league_name] = w_league

        # Collect all teams in the season (from any fixture, scheduled or finished)
        # so the dropdown CSV stays current even before games are played.
        season_teams: list[str] = []
        for m in matches:
            home_csv = FD_TO_CSV.get(m['homeTeam']['name'], m['homeTeam']['name'])
            away_csv = FD_TO_CSV.get(m['awayTeam']['name'], m['awayTeam']['name'])
            season_teams.append(home_csv)
            season_teams.append(away_csv)
        update_teams_csv(league_name, season_teams)

        # Aggregate goals from finished matches
        team_results: dict[str, dict] = {}
        for m in matches:
            if m.get('status') != 'FINISHED':
                continue
            ft = m.get('score', {}).get('fullTime', {})
            hg, ag = ft.get('home'), ft.get('away')
            if hg is None or ag is None:
                continue
            home_csv = FD_TO_CSV.get(m['homeTeam']['name'], m['homeTeam']['name'])
            away_csv = FD_TO_CSV.get(m['awayTeam']['name'], m['awayTeam']['name'])
            for team, gf, ga in [(home_csv, hg, ag), (away_csv, ag, hg)]:
                team_results.setdefault(team, {'gf': 0, 'ga': 0, 'games': 0})
                team_results[team]['gf']    += gf
                team_results[team]['ga']    += ga
                team_results[team]['games'] += 1

        if team_results:
            league_results[league_name] = team_results
            print(f'[{code}] {len(team_results)} teams have played games.')
        else:
            print(f'[{code}] Season not started yet — no stat update.')

    if league_results:
        update_csv(league_results, league_wratings)

    stats = load_stats()
    if all_matches:
        generate_today_json(all_matches, stats)
        save_to_firestore(all_matches, stats)


if __name__ == '__main__':
    main()
