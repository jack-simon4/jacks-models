"""
Generate NFL game picks for the current week and write nfl-picks.json.
Uses NFL-Stats.csv (team ratings) and NFL-Spreads.csv (matchups + lines).

NFL-Spreads.csv format: Team, Spread, Opponent, GameTime (UTC)
  Spread is from the team's perspective (negative = favorite).
  If Opponent/GameTime columns are absent the script skips that row.

Output: src/assets/nfl-picks.json
  List of game objects:
  { homeTeam, awayTeam, homePredicted, awayPredicted,
    pick, winProb, spread, gameTime, confidence }
"""

import csv
import json
import math
import os

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_PATH = os.path.join(ASSETS, 'NFL-Stats.csv')
SPREAD_PATH= os.path.join(ASSETS, 'NFL-Spreads.csv')
OUT_PATH   = os.path.join(ASSETS, 'nfl-picks.json')

HOME_ADV   = 2.5   # points
WIN_PROB_K = 0.30


def load_stats() -> dict:
    stats = {}
    with open(STATS_PATH, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                stats[row['Team']] = {
                    'offPPG':  float(row.get('offPPG',  row.get('OffPPG',  0))),
                    'defPPG':  float(row.get('defPPG',  row.get('DefPPG',  0))),
                    'offYPG':  float(row.get('offYPG',  row.get('OffYPG',  0))),
                    'defYPG':  float(row.get('defYPG',  row.get('DefYPG',  0))),
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
        has_game_time = 'GameTime' in fieldnames
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

        picks.append({
            'homeTeam':      home_name,
            'awayTeam':      away_name,
            'homePredicted': h_score,
            'awayPredicted': a_score,
            'pick':          pick,
            'winProb':       wp if pick == home_name else round(1 - wp, 3),
            'spread':        m['spread'],
            'gameTime':      m['gameTime'],
            'confidence':    confidence,
        })

    picks.sort(key=lambda p: p['winProb'], reverse=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)
    print(f'[NFL Picks] Wrote {len(picks)} picks to nfl-picks.json.')


if __name__ == '__main__':
    main()
