"""
Generate src/app/generated/picks-data.ts from the current JSON picks files.

Run before `npm run prerender` so the weekly-picks page is prerendered with
real data. Called by the daily-deploy GitHub Actions workflow.

Output format: a TypeScript `const` that the WeeklyPicksComponent imports
statically — no HttpClient, no Firestore, guaranteed prerender-time data.
"""

import json
import os
import re
from datetime import datetime, timezone

ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
OUT    = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'app', 'generated', 'picks-data.ts'))

# ── helpers ────────────────────────────────────────────────────────────────

def fmt_line(spread, home_team, away_team):
    """Format a spread as 'Team -X' or \"pick 'em\"."""
    if spread is None:
        return None
    spread = round(spread, 1)
    if abs(spread) < 0.5:
        return "pick 'em"
    if spread > 0:
        return f"{home_team} -{abs(spread)}"
    return f"{away_team} -{abs(spread)}"


def pick_entry(away, home, away_pred, home_pred, pick, win_prob, confidence,
               vegas_spread, spread_edge, game_time):
    away_r = round(away_pred)
    home_r = round(home_pred)
    model_diff = home_pred - away_pred

    if pick == home:
        projection = f"{home} {home_r}, {away} {away_r}"
    else:
        projection = f"{away} {away_r}, {home} {home_r}"

    model_line = fmt_line(model_diff, home, away)
    vegas_line = fmt_line(vegas_spread, home, away)

    if spread_edge is not None and abs(spread_edge) >= 1.0:
        edge_note = f"{abs(spread_edge):.1f}-point model edge toward {pick}"
    else:
        edge_note = None

    game_date = game_time[:10] if game_time else ''

    return {
        'gameDate':   game_date,
        'matchup':    f"{away} at {home}",
        'projection': projection,
        'pick':       pick,
        'winPct':     round(win_prob * 100),
        'confidence': confidence,
        'vegasLine':  vegas_line,
        'modelLine':  model_line,
        'edgeNote':   edge_note,
    }


def load_picks(filename, min_confidence=('Elite', 'Strong', 'Lean')):
    path = os.path.join(ASSETS, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    return [p for p in (raw if isinstance(raw, list) else []) if p.get('confidence') in min_confidence]


def js_string(s):
    """Escape a Python string for embedding in a JS/TS string literal."""
    return s.replace('\\', '\\\\').replace("'", "\\'") if s else ''


def js_val(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return f"'{js_string(v)}'"
    return str(v)


def render_pick(p):
    lines = []
    for key in ('gameDate', 'matchup', 'projection', 'pick', 'confidence',
                'vegasLine', 'modelLine', 'edgeNote'):
        lines.append(f"        {key}: {js_val(p[key])},")
    lines.append(f"        winPct: {js_val(p['winPct'])},")
    return '      {\n' + '\n'.join(lines) + '\n      }'


def render_sport_block(sport_label, week_label, picks):
    picks_ts = ',\n'.join(render_pick(p) for p in picks)
    return (
        f"  {{\n"
        f"    sport: '{js_string(sport_label)}',\n"
        f"    weekLabel: '{js_string(week_label)}',\n"
        f"    picks: [\n{picks_ts}\n    ],\n"
        f"  }}"
    )


# ── main ───────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc)
    today = now.strftime('%Y-%m-%d')

    sports = []

    # NFL
    nfl_raw = load_picks('nfl-picks.json')
    if nfl_raw:
        entries = [pick_entry(
            p['awayTeam'], p['homeTeam'],
            p['predictedAwayScore'], p['predictedHomeScore'],
            p['pick'], p['winProb'], p['confidence'],
            p.get('vegasSpread'), p.get('spreadEdge'), p.get('gameTime', '')
        ) for p in nfl_raw[:8]]
        sports.append(render_sport_block('NFL', f'NFL — {today}', entries))

    # NCAAF
    ncaaf_raw = load_picks('ncaaf-picks.json')
    if ncaaf_raw:
        entries = [pick_entry(
            p['awayTeam'], p['homeTeam'],
            p['predictedAwayScore'], p['predictedHomeScore'],
            p['pick'], p['winProb'], p['confidence'],
            p.get('vegasSpread'), p.get('spreadEdge'), p.get('gameTime', '')
        ) for p in ncaaf_raw[:8]]
        sports.append(render_sport_block('NCAAF', f'College Football — {today}', entries))

    # NBA
    nba_raw = load_picks('nba-picks.json')
    if nba_raw:
        entries = [pick_entry(
            p['awayTeam'], p['homeTeam'],
            p['predictedAwayScore'], p['predictedHomeScore'],
            p['pick'], p['winProb'], p['confidence'],
            p.get('vegasSpread'), p.get('spreadEdge'), p.get('gameTime', '')
        ) for p in nba_raw[:8]]
        sports.append(render_sport_block('NBA', f'NBA — {today}', entries))

    # NCAAM
    ncaam_raw = load_picks('ncaam-picks.json')
    if ncaam_raw:
        entries = [pick_entry(
            p['awayTeam'], p['homeTeam'],
            p['predictedAwayScore'], p['predictedHomeScore'],
            p['pick'], p['winProb'], p['confidence'],
            p.get('vegasSpread'), p.get('spreadEdge'), p.get('gameTime', '')
        ) for p in ncaam_raw[:8]]
        sports.append(render_sport_block('NCAAM', f'College Basketball — {today}', entries))

    # NHL
    nhl_raw = load_picks('nhl-picks.json')
    if nhl_raw:
        entries = [pick_entry(
            p['awayTeam'], p['homeTeam'],
            p.get('predictedAwayScore', 0), p.get('predictedHomeScore', 0),
            p['pick'], p.get('winProb', 0.5), p['confidence'],
            None, None, p.get('gameTime', '')
        ) for p in nhl_raw[:6]]
        sports.append(render_sport_block('NHL', f'NHL — {today}', entries))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    ts_content = (
        f"// AUTO-GENERATED by scripts/generate_picks_content.py — do not edit manually\n"
        f"// Generated: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n"
        f"export const WEEKLY_PICKS: {{\n"
        f"  generatedAt: string;\n"
        f"  sports: {{\n"
        f"    sport: string; weekLabel: string;\n"
        f"    picks: {{\n"
        f"      gameDate: string; matchup: string; projection: string;\n"
        f"      pick: string; winPct: number; confidence: string;\n"
        f"      vegasLine: string | null; modelLine: string | null; edgeNote: string | null;\n"
        f"    }}[];\n"
        f"  }}[];\n"
        f"}} = {{\n"
        f"  generatedAt: '{today}',\n"
        f"  sports: [\n"
        + ',\n'.join(sports) +
        f"\n  ],\n"
        f"}};\n"
    )

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(ts_content)

    print(f'[Picks Content] Wrote {len(sports)} sport(s), {today}')


if __name__ == '__main__':
    main()
