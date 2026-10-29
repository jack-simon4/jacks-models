"""
Generate NFL player props for the current week's games.

Replicates the scoreboard matchup formula to project:
  - QB passing yards + TDs
  - RB rushing yards + TDs
  - WR/TE receiving yards + TDs

Outputs src/assets/nfl-player-props.json — a list of the top projected
performers across all this week's games, sorted by projected yards.
"""

import csv
import json
import math
import os
import sys

ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))

# ── League averages (must match scoreboard.component.ts nflLeagueAvg) ──────────
LG = {
    'rushYPA': 4.44,
    'rushAtt': 26.95,
    'passYPA': 7.175,
    'passAtt': 32.69,
}

def _safe(val, fallback=0.0):
    try:
        v = float(val)
        return v if math.isfinite(v) else fallback
    except (TypeError, ValueError):
        return fallback

def load_team_stats():
    path = os.path.join(ASSETS, 'NFL-Stats.csv')
    teams = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = row['Team'].strip()
            teams[name] = {
                'rushYPA':      _safe(row.get('RushYdsAtt')),
                'dRushYPA':     _safe(row.get('dRushYdsAtt')),
                'passYPA':      _safe(row.get('PassYdsAtt')),
                'dPassYPA':     _safe(row.get('dPassYdsAtt')),
                'oRushPG':      _safe(row.get('oRushPerGame')),
                'dRushPG':      _safe(row.get('dRushPerGame')),
                'oPassPG':      _safe(row.get('oPassPerGame')),
                'dPassPG':      _safe(row.get('dPassPerGame')),
            }
    return teams

def load_qbs():
    path = os.path.join(ASSETS, 'NFL-QBs.csv')
    qbs = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            team = row['Team'].strip()
            qbs[team] = {
                'name':       row['Name'].strip(),
                'passYPA':    _safe(row.get('PassYdsAtt')),
                'passAPG':    _safe(row.get('PassAttGame')),
                'tdRate':     _safe(row.get('TDRate')),
            }
    return qbs

def load_rbs():
    path = os.path.join(ASSETS, 'NFL-RBs.csv')
    rbs: dict[str, list] = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            team = row['Team'].strip()
            rbs.setdefault(team, []).append({
                'name':     row['Name'].strip(),
                'ypc':      _safe(row.get('RushYdsCarry')),
                'attPG':    _safe(row.get('RushAttGame')),
                'tdGame':   _safe(row.get('TDGame')),
            })
    return rbs

def load_receivers():
    path = os.path.join(ASSETS, 'NFL-Receivers.csv')
    recs: dict[str, list] = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            team = row['Team'].strip()
            recs.setdefault(team, []).append({
                'name':      row['Name'].strip(),
                'position':  row.get('Position', 'WR').strip(),
                'tgtPG':     _safe(row.get('TargetsGame')),
                'ydPerTgt':  _safe(row.get('RecYdTarget')),
                'tdGame':    _safe(row.get('TDGame')),
                'recPG':     _safe(row.get('RecGame')),
            })
    return recs

def project_game(home, away, team_stats, qbs, rbs, receivers, game_time):
    ht = team_stats.get(home, {})
    at = team_stats.get(away, {})
    if not ht or not at:
        return []

    # ── Passing matchup factors ────────────────────────────────────────────────
    def pass_factor(off_team, def_team):
        qb   = qbs.get(off_team, {})
        ypa  = qb.get('passYPA') or ht.get('passYPA') or LG['passYPA']
        apg  = qb.get('passAPG') or ht.get('oPassPG') or LG['passAtt']
        d    = team_stats[def_team]
        adj_ypa = .85 * ypa * (d['dPassYPA'] / LG['passYPA']) + .15 * LG['passYPA']
        adj_att = .85 * apg  * (d['dPassPG']  / LG['passAtt']) + .15 * LG['passAtt']
        proj_yds = adj_ypa * adj_att
        raw_yds  = ypa * apg
        factor   = proj_yds / raw_yds if raw_yds > 0 else 1.0
        return proj_yds, adj_att, factor

    def rush_factor(off_team, def_team):
        o = team_stats[off_team]
        d = team_stats[def_team]
        team_rbs = rbs.get(off_team, [])
        if team_rbs:
            total_att = sum(r['attPG'] for r in team_rbs)
            w_ypc = (sum(r['ypc'] * r['attPG'] for r in team_rbs) / total_att
                     if total_att > 0 else o['rushYPA'])
        else:
            w_ypc = o['rushYPA']
        adj_ypc = .85 * w_ypc         * (d['dRushYPA'] / LG['rushYPA']) + .15 * LG['rushYPA']
        adj_att = .85 * o['oRushPG']  * (d['dRushPG']  / LG['rushAtt']) + .15 * LG['rushAtt']
        proj_yds = adj_ypc * adj_att
        raw_yds  = w_ypc * o['oRushPG']
        factor   = proj_yds / raw_yds if raw_yds > 0 else 1.0
        return factor

    results = []

    for off_team, def_team, side in [(home, away, 'home'), (away, home, 'away')]:
        proj_pass_yds, proj_att, pass_f = pass_factor(off_team, def_team)
        rush_f = rush_factor(off_team, def_team)

        # QB
        qb = qbs.get(off_team)
        if qb:
            proj_tds = round(qb['tdRate'] * proj_att, 2)
            results.append({
                'name':      qb['name'],
                'team':      off_team,
                'opponent':  def_team,
                'position':  'QB',
                'projYards': round(proj_pass_yds),
                'projTDs':   proj_tds,
                'statLabel': 'Pass Yds',
                'matchup':   f'{away} @ {home}',
                'gameTime':  game_time,
            })

        # RBs
        for rb in (rbs.get(off_team) or []):
            yds = rb['ypc'] * rb['attPG'] * rush_f
            tds = round(rb['tdGame'] * rush_f, 2)
            results.append({
                'name':      rb['name'],
                'team':      off_team,
                'opponent':  def_team,
                'position':  'RB',
                'projYards': round(yds),
                'projTDs':   tds,
                'statLabel': 'Rush Yds',
                'matchup':   f'{away} @ {home}',
                'gameTime':  game_time,
            })

        # Receivers
        for rec in (receivers.get(off_team) or []):
            yds = rec['ydPerTgt'] * rec['tgtPG'] * pass_f
            tds = round(rec['tdGame'] * pass_f, 2)
            results.append({
                'name':      rec['name'],
                'team':      off_team,
                'opponent':  def_team,
                'position':  rec['position'],
                'projYards': round(yds),
                'projTDs':   tds,
                'statLabel': 'Rec Yds',
                'matchup':   f'{away} @ {home}',
                'gameTime':  game_time,
            })

    return results

def main():
    picks_path = os.path.join(ASSETS, 'nfl-picks.json')
    out_path   = os.path.join(ASSETS, 'nfl-player-props.json')

    with open(picks_path, encoding='utf-8') as f:
        picks = json.load(f)

    team_stats = load_team_stats()
    qbs        = load_qbs()
    rbs        = load_rbs()
    receivers  = load_receivers()

    all_props = []
    for game in picks:
        home = game.get('homeTeam', '')
        away = game.get('awayTeam', '')
        gt   = game.get('gameTime', '')
        props = project_game(home, away, team_stats, qbs, rbs, receivers, gt)
        all_props.extend(props)

    # Bucket by position, dedupe names within each bucket, keep top N per position
    PER_POSITION = {'QB': 5, 'RB': 5, 'WR': 5, 'TE': 5}
    buckets: dict[str, list] = {pos: [] for pos in PER_POSITION}
    seen: dict[str, set] = {pos: set() for pos in PER_POSITION}

    for p in sorted(all_props, key=lambda x: x['projYards'], reverse=True):
        pos = p['position']
        if pos not in buckets:
            continue
        if p['name'] not in seen[pos]:
            seen[pos].add(p['name'])
            buckets[pos].append(p)

    # Combine in display order: QB, RB, WR, TE
    top = []
    for pos in PER_POSITION:
        top.extend(buckets[pos][:PER_POSITION[pos]])

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(top, f, indent=2)

    print(f'[NFLProps] Wrote {len(top)} props -> {out_path}')
    for p in top[:5]:
        print(f"  {p['name']} ({p['position']}, {p['team']}): {p['projYards']} {p['statLabel']}, {p['projTDs']} TDs")

if __name__ == '__main__':
    main()
