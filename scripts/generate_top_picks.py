"""
Generate today's MLB top picks by running the full scoreboard model for
every scheduled game and ranking results by win-probability edge.

Outputs: src/assets/top-picks.json

The model is a direct Python port of the TypeScript MLB case in
ScoreboardComponent.runSimulation().  All formulas, league averages,
and park-factor applications are kept identical so predicted scores
match what the interactive scoreboard would produce.

Note: The TypeScript ballpark parser reads wSO and wBB in swapped
column positions.  We replicate that here so scores stay consistent.
"""

import json
import math
import os
import unicodedata
from datetime import date

import pandas as pd
import statsapi

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fb_firestore
    _FIREBASE_AVAILABLE = True
except ImportError:
    _FIREBASE_AVAILABLE = False

# ── Paths ──────────────────────────────────────────────────────────────────
ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
OUTPUT = os.path.join(ASSETS, 'top-picks.json')

# ── Model constants (match TypeScript LG_AVG_PITCHER / LG_AVG_BATTER) ─────
PA_SLOTS = [4.65, 4.55, 4.43, 4.33, 4.24, 4.13, 4.01, 3.9, 3.77]

LG_AVG = {
    'k_percent': 22.7, 'bb_percent': 8.3,
    'xba': 0.248, 'xslg': 0.394, 'xobp': 0.320,
    'single_pct': 0.1343, 'double_pct': 0.0409,
    'triple_pct': 0.00367, 'hr_pct': 0.02555,
    'pa_per_game': 27.0, 'hand': 'R',
    'wRops': 1.0, 'wLops': 1.0,
}

# Win-probability logistic scale factor.
# Calibrated to MLB empirical data: 1-run expected advantage ≈ 57% actual win rate.
# K=0.30 gives sigmoid(0.30*1) ≈ 0.574, matching that baseline.
# Previous value of 0.45 was systematically overconfident.
WIN_PROB_K = 0.30


# ── Helpers ────────────────────────────────────────────────────────────────
def _ascii(name: str) -> str:
    return unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode('ascii')


def _fv(val, fallback: float) -> float:
    """Return val as float if truthy and finite, else fallback."""
    try:
        v = float(val)
        return v if math.isfinite(v) and v != 0 else fallback
    except (TypeError, ValueError):
        return fallback


def log5(b: float, p: float, l: float) -> float:
    """True log5 formula — matches scoreboard.component.ts exactly."""
    if l <= 0 or l >= 1 or b <= 0 or p <= 0:
        return 0.0
    bp  = (b * p) / l
    neg = ((1 - b) * (1 - p)) / (1 - l)
    return bp / (bp + neg)


def win_prob(home_runs: float, away_runs: float) -> float:
    diff = home_runs - away_runs
    return 1.0 / (1.0 + math.exp(-WIN_PROB_K * diff))


def prob_to_american(prob: float) -> str:
    prob = max(0.01, min(0.99, prob))
    if prob >= 0.5:
        raw = -(prob / (1 - prob)) * 100
        val = int(round(raw / 5) * 5)
        return str(val)
    else:
        raw = ((1 - prob) / prob) * 100
        val = int(round(raw / 5) * 5)
        return f'+{val}'


def confidence_label(edge: float):
    """edge = win_prob - 0.5.  Returns None if below minimum threshold.
    Lean tier removed — too low a bar to be meaningful predictors."""
    if edge >= 0.14:
        return 'Elite'
    if edge >= 0.08:
        return 'Strong'
    return None


def save_picks_to_firestore(picks: list):
    """Write today's qualifying picks to Firestore. No-op if creds unavailable."""
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        print('[TopPicks] FIREBASE_SERVICE_ACCOUNT not set — skipping Firestore save.')
        return
    if not _FIREBASE_AVAILABLE:
        print('[TopPicks] firebase-admin not installed — skipping Firestore save.')
        return

    cred = credentials.Certificate(json.loads(sa_json))
    app = firebase_admin.initialize_app(cred)
    db = fb_firestore.client()

    saved = 0
    for pick in picks:
        game_pk = pick.get('gamePk')
        if not game_pk:
            continue
        doc_ref = db.collection('games').document(str(game_pk))
        # Only create — never overwrite a doc that already has actual scores
        if not doc_ref.get().exists:
            doc_ref.set({
                'sport': 'MLB',
                'homeTeam': pick['homeTeam'],
                'awayTeam': pick['awayTeam'],
                'predictedHomeScore': pick['predictedHomeScore'],
                'predictedAwayScore': pick['predictedAwayScore'],
                'actualHomeScore': None,
                'actualAwayScore': None,
                'pick': pick['pick'],
                'winProb': pick['winProb'],
                'odds': pick['odds'],
                'confidence': pick['confidence'],
                'gamePk': game_pk,
                'gameTime': pick['gameTime'],
                'awayPitcher': pick.get('awayPitcher', ''),
                'homePitcher': pick.get('homePitcher', ''),
                'timestamp': fb_firestore.SERVER_TIMESTAMP,
            })
            saved += 1
            print(f'  [Firestore] Saved: {pick["awayTeam"]} @ {pick["homeTeam"]}')

    firebase_admin.delete_app(app)
    print(f'[TopPicks] {saved} new picks written to Firestore.')


# ── Data loaders ───────────────────────────────────────────────────────────
def load_vegas_odds() -> dict:
    """Load pre-fetched Vegas moneylines from MLB-Odds.json.
    Returns {home_team_name: {'home_ml': '-145', 'away_ml': '+125', ...}}."""
    odds_path = os.path.join(ASSETS, 'MLB-Odds.json')
    if not os.path.exists(odds_path):
        print('[TopPicks] MLB-Odds.json not found — no Vegas odds available.')
        return {}
    try:
        with open(odds_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f'[TopPicks] Loaded Vegas odds for {len(data)} games.')
        return data
    except Exception as exc:
        print(f'[TopPicks] Failed to load MLB-Odds.json: {exc}')
        return {}


def vegas_favorite(odds_entry: dict | None, home_team: str, away_team: str) -> str | None:
    """Return the Vegas-favored team name, or None if no line available."""
    if not odds_entry:
        return None
    try:
        home_ml = int(odds_entry['home_ml'])
        away_ml = int(odds_entry['away_ml'])
    except (KeyError, ValueError, TypeError):
        return None
    if home_ml < away_ml:
        return home_team
    elif away_ml < home_ml:
        return away_team
    return None  # pick'em / exactly equal


def load_pitchers() -> dict:
    """Returns {ascii_name: stat_dict}."""
    df = pd.read_csv(os.path.join(ASSETS, 'MLB-Pitchers.csv'), encoding='utf-8')
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        'single%': 'single_pct', 'double%': 'double_pct',
        'triple%': 'triple_pct', 'home_run%': 'hr_pct',
        'PA/G': 'pa_per_game', 'Hand': 'hand',
    }
    df = df.rename(columns=col_map)
    result = {}
    for _, row in df.iterrows():
        key = _ascii(str(row.get('Name', '')))
        result[key] = row.to_dict()
    print(f'[TopPicks] Loaded {len(result)} pitchers.')
    return result


def load_hitters() -> dict:
    """Returns {ascii_name: stat_dict}."""
    df = pd.read_csv(os.path.join(ASSETS, 'MLB-Hitters.csv'), encoding='utf-8')
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        'single%': 'single_pct', 'double%': 'double_pct',
        'triple%': 'triple_pct', 'home_run%': 'hr_pct',
    }
    df = df.rename(columns=col_map)
    result = {}
    for _, row in df.iterrows():
        key = _ascii(str(row.get('Name', '')))
        result[key] = row.to_dict()
    print(f'[TopPicks] Loaded {len(result)} hitters.')
    return result


def load_ballparks() -> dict:
    """
    Returns {team_name: park_factor_dict}.

    The TypeScript parser reads the CSV positionally with wBB and wSO in
    swapped positions relative to the actual CSV header.  We mirror that
    swap here so simulated scores stay consistent with the scoreboard.
    CSV column order:  Team, w1B, w2B, w3B, wHR, wSO, wBB, wRest, wOBP, TB_R
    TypeScript names:  team, w1B, w2B, w3B, wHR, wBB, wSO, wRest, wOBP, TB_R
    """
    df = pd.read_csv(os.path.join(ASSETS, 'MLB-Ballparks.csv'), encoding='utf-8')
    df.columns = [c.strip() for c in df.columns]
    result = {}
    for _, row in df.iterrows():
        team = str(row.iloc[0]).strip()
        result[team] = {
            'w1B':   float(row.get('w1B',   1.0) or 1.0),
            'w2B':   float(row.get('w2B',   1.0) or 1.0),
            'w3B':   float(row.get('w3B',   1.0) or 1.0),
            'wHR':   float(row.get('wHR',   1.0) or 1.0),
            # Intentionally swapped to match TypeScript positional parser:
            'wBB':   float(row.get('wSO',   1.0) or 1.0),
            'wSO':   float(row.get('wBB',   1.0) or 1.0),
            'wRest': float(row.get('wRest', 1.0) or 1.0),
            'wOBP':  float(row.get('wOBP',  1.0) or 1.0),
            'TB_R':  float(row.get('TB_R',  3.0) or 3.0),
        }
    print(f'[TopPicks] Loaded {len(result)} ballparks.')
    return result


def load_lineups() -> dict:
    """Returns {'TeamName1': 'Player Name', 'TeamName2': ...}."""
    df = pd.read_csv(os.path.join(ASSETS, 'MLB-Lineups.csv'), encoding='utf-8')
    result = {}
    for _, row in df.iterrows():
        result[str(row['Team']).strip()] = str(row['Player']).strip()
    return result


# ── Stat fill helpers (match TypeScript fillPitcher / fillBatter) ──────────
def fill_pitcher(raw: dict | None) -> dict:
    out = dict(LG_AVG)
    if raw:
        for field, lg in [
            ('k_percent', LG_AVG['k_percent']), ('bb_percent', LG_AVG['bb_percent']),
            ('xba', LG_AVG['xba']),             ('xslg', LG_AVG['xslg']),
            ('xobp', LG_AVG['xobp']),
            ('single_pct', LG_AVG['single_pct']), ('double_pct', LG_AVG['double_pct']),
            ('triple_pct', LG_AVG['triple_pct']), ('hr_pct', LG_AVG['hr_pct']),
        ]:
            out[field] = _fv(raw.get(field), lg)
        out['hand'] = str(raw.get('hand', 'R') or 'R').strip() or 'R'
    return out


def fill_batter(raw: dict | None) -> dict:
    out = dict(LG_AVG)
    if raw:
        for field, lg in [
            ('k_percent', LG_AVG['k_percent']), ('bb_percent', LG_AVG['bb_percent']),
            ('xba', LG_AVG['xba']),             ('xslg', LG_AVG['xslg']),
            ('xobp', LG_AVG['xobp']),
            ('single_pct', LG_AVG['single_pct']), ('double_pct', LG_AVG['double_pct']),
            ('triple_pct', LG_AVG['triple_pct']), ('hr_pct', LG_AVG['hr_pct']),
            ('wRops', 1.0), ('wLops', 1.0),
        ]:
            out[field] = _fv(raw.get(field), lg)
    return out


# ── Core model ─────────────────────────────────────────────────────────────
def _team_score(batters: list, opp_pitcher: dict, opp_hand: str,
                park: dict, is_home: bool) -> float:
    """
    Compute expected runs for one team — direct port of the TypeScript MLB
    model inner loop (lines 1299-1452 of scoreboard.component.ts).
    """
    xbases_list = []

    for i, b in enumerate(batters):
        platoon     = b['wRops'] if opp_hand == 'R' else b['wLops']
        platoon_rev = b['wLops'] if opp_hand == 'R' else b['wRops']  # strikeouts reversed

        single = log5(b['single_pct'], opp_pitcher['single_pct'], 0.13425) * platoon * park['w1B']
        double = log5(b['double_pct'], opp_pitcher['double_pct'], 0.0409)  * platoon * park['w2B']
        triple = log5(b['triple_pct'], opp_pitcher['triple_pct'], 0.00367) * platoon * park['w3B']
        hr     = log5(b['hr_pct'],     opp_pitcher['hr_pct'],     0.02555) * platoon * park['wHR']
        _k     = log5(b['k_percent'] / 100, opp_pitcher['k_percent'] / 100, 0.21377) * platoon_rev * park['wSO']  # noqa: F841
        bb     = log5(b['bb_percent'] / 100, opp_pitcher['bb_percent'] / 100, 0.093317) * platoon * park['wBB']
        ab     = PA_SLOTS[i] * (1 - bb)
        xslg   = (b['xslg'] * (opp_pitcher['xslg'] / 0.3878)) * platoon

        # xBases per batter — rounded to 2dp like TypeScript's .toFixed(2)
        xb = round(
            ((xslg * ab) + ((single + double * 2 + triple * 3 + hr * 4) * PA_SLOTS[i])) / 2 - 0.19,
            2,
        )
        xbases_list.append(max(xb, 0.0))

    offset = 0.125 if is_home else 0.175
    return math.floor(sum(xbases_list)) / park['TB_R'] - offset


def simulate_game(
    home_team: str, away_team: str,
    home_pitcher_name: str, away_pitcher_name: str,
    pitchers: dict, hitters: dict, ballparks: dict, lineups: dict,
) -> tuple[float, float]:
    """Returns (home_expected_runs, away_expected_runs)."""

    # Resolve park — try exact match then partial
    park = ballparks.get(home_team)
    if park is None:
        for k, v in ballparks.items():
            if k in home_team or home_team in k:
                park = v
                break
    if park is None:
        park = {k: 1.0 for k in ('w1B','w2B','w3B','wHR','wBB','wSO','wRest','wOBP')} | {'TB_R': 3.0}

    # Resolve pitchers
    hp = fill_pitcher(pitchers.get(_ascii(home_pitcher_name)) if home_pitcher_name else None)
    ap = fill_pitcher(pitchers.get(_ascii(away_pitcher_name)) if away_pitcher_name else None)

    # Resolve lineups (9 batters each)
    home_batters = [
        fill_batter(hitters.get(_ascii(lineups.get(f'{home_team}{i}', ''))))
        for i in range(1, 10)
    ]
    away_batters = [
        fill_batter(hitters.get(_ascii(lineups.get(f'{away_team}{i}', ''))))
        for i in range(1, 10)
    ]

    home_runs = _team_score(home_batters, ap, ap['hand'], park, is_home=True)
    away_runs = _team_score(away_batters, hp, hp['hand'], park, is_home=False)
    return home_runs, away_runs


# ── Main ───────────────────────────────────────────────────────────────────
def generate_top_picks():
    today = date.today().strftime('%m/%d/%Y')
    print(f'[TopPicks] Generating picks for {today}')

    pitchers    = load_pitchers()
    hitters     = load_hitters()
    ballparks   = load_ballparks()
    lineups     = load_lineups()
    vegas_odds  = load_vegas_odds()

    try:
        schedule = statsapi.schedule(date=today, sportId=1)
    except Exception as exc:
        print(f'[TopPicks] Failed to fetch schedule: {exc}')
        schedule = []

    if not schedule:
        print('[TopPicks] No games today — writing empty picks file.')
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
        return

    print(f'[TopPicks] {len(schedule)} games today.')
    picks = []

    for game in schedule:
        away_name    = game.get('away_name', '')
        home_name    = game.get('home_name', '')
        away_pitcher = (game.get('away_probable_pitcher') or '').strip()
        home_pitcher = (game.get('home_probable_pitcher') or '').strip()
        game_time    = game.get('game_datetime', '')
        game_pk      = game.get('game_id')
        status       = game.get('status', '')

        print(f'  [{status}] {away_name} @ {home_name}  '
              f'SP: {away_pitcher or "TBD"} vs {home_pitcher or "TBD"}')

        try:
            home_runs, away_runs = simulate_game(
                home_name, away_name, home_pitcher, away_pitcher,
                pitchers, hitters, ballparks, lineups,
            )
        except Exception as exc:
            print(f'    Simulation failed: {exc}')
            continue

        home_wp = win_prob(home_runs, away_runs)
        away_wp = 1.0 - home_wp

        if home_wp >= away_wp:
            pick_team, pick_wp = home_name, home_wp
        else:
            pick_team, pick_wp = away_name, away_wp

        edge  = pick_wp - 0.5
        label = confidence_label(edge)
        if label is None:
            print(f'    Edge {edge:.3f} below threshold — skipping.')
            continue

        # Vegas consensus filter: only keep picks where Vegas agrees on winner.
        # If no odds are available, skip the consensus check and keep the pick.
        game_odds = vegas_odds.get(home_name)
        vfav = vegas_favorite(game_odds, home_name, away_name)
        if vfav is not None and vfav != pick_team:
            print(f'    Model favors {pick_team} but Vegas favors {vfav} — skipping (no consensus).')
            continue

        # Use real Vegas odds if available; fall back to model-derived odds
        if game_odds:
            if pick_team == home_name:
                odds = game_odds['home_ml']
            else:
                odds = game_odds['away_ml']
            print(f'    Using Vegas odds: {pick_team} {odds}')
        else:
            odds = prob_to_american(pick_wp)
            print(f'    No Vegas line — using model odds: {pick_team} {odds}')

        picks.append({
            'matchup':             f'{away_name} @ {home_name}',
            'awayTeam':            away_name,
            'homeTeam':            home_name,
            'awayPitcher':         away_pitcher or 'TBD',
            'homePitcher':         home_pitcher or 'TBD',
            'pick':                pick_team,
            'prediction':          f'{pick_team} {odds}',
            'odds':                odds,
            'winProb':             round(pick_wp, 3),
            'edge':                round(edge, 3),
            'confidence':          label,
            'predictedScore':      f'{away_name} {away_runs:.1f} – {home_name} {home_runs:.1f}',
            'predictedHomeScore':  round(home_runs, 2),
            'predictedAwayScore':  round(away_runs, 2),
            'gameTime':            game_time,
            'gamePk':              game_pk,
        })

    picks.sort(key=lambda x: x['edge'], reverse=True)
    for i, p in enumerate(picks):
        p['rank'] = i + 1

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)
    print(f'[TopPicks] Saved {len(picks)} qualifying picks -> {OUTPUT}')

    save_picks_to_firestore(picks)


if __name__ == '__main__':
    generate_top_picks()
