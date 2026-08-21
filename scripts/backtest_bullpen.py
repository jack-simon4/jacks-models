"""
Backtest the bullpen-scaling improvement against completed MLB games in Firestore.

For each completed game stored in Firestore (has actualHomeScore) we:
  1. Re-run simulate_game() using the stored pitcher names + current lineups
  2. Apply the new bullpen RA/G scaling
  3. Compare old pick (stored) vs new pick (re-simulated) vs actual winner

Prints a side-by-side accuracy table so you can see whether the new model
improves on the old one.

Usage:
    FIREBASE_SERVICE_ACCOUNT=<json> python scripts/backtest_bullpen.py
"""

import json
import os
import sys

# Allow importing from generate_top_picks without running main()
sys.path.insert(0, os.path.dirname(__file__))
from generate_top_picks import (
    simulate_game, fetch_team_rapg,
    BULLPEN_WEIGHT, LEAGUE_AVG_RPG,
    load_pitchers, load_hitters, load_ballparks, load_lineups,
    win_prob,
)

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fb_firestore
except ImportError:
    print('[Backtest] firebase-admin not installed.')
    sys.exit(1)

from datetime import date
from collections import defaultdict


def load_completed_games(db) -> list:
    docs = db.collection('games').where('sport', '==', 'MLB').stream()
    games = []
    for doc in docs:
        d = doc.to_dict()
        if d.get('actualHomeScore') is not None and d.get('actualAwayScore') is not None:
            games.append(d)
    return games


def resimulate(game: dict, pitchers, hitters, ballparks, lineups, team_rapg) -> dict | None:
    home = game.get('homeTeam', '')
    away = game.get('awayTeam', '')
    home_sp = game.get('homePitcher', '')
    away_sp = game.get('awayPitcher', '')

    if not home or not away:
        return None

    try:
        home_woba, away_woba = simulate_game(
            home, away, home_sp, away_sp,
            pitchers, hitters, ballparks, lineups,
        )
    except Exception as exc:
        print(f'  [skip] {away} @ {home}: {exc}')
        return None

    if team_rapg:
        home_rapg = team_rapg.get(home, LEAGUE_AVG_RPG)
        away_rapg = team_rapg.get(away, LEAGUE_AVG_RPG)
        home_runs = round(home_woba * (1 - BULLPEN_WEIGHT + BULLPEN_WEIGHT * (away_rapg / LEAGUE_AVG_RPG)), 2)
        away_runs = round(away_woba * (1 - BULLPEN_WEIGHT + BULLPEN_WEIGHT * (home_rapg / LEAGUE_AVG_RPG)), 2)
    else:
        home_runs, away_runs = home_woba, away_woba

    home_wp = win_prob(home_runs, away_runs)
    new_pick = home if home_wp >= 0.5 else away
    return {'new_pick': new_pick, 'home_wp': home_wp}


def main():
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        print('[Backtest] FIREBASE_SERVICE_ACCOUNT not set.')
        sys.exit(1)

    cred = credentials.Certificate(json.loads(sa_json))
    app = firebase_admin.initialize_app(cred)
    db = fb_firestore.client()

    print('[Backtest] Loading completed games from Firestore...')
    games = load_completed_games(db)
    firebase_admin.delete_app(app)
    print(f'[Backtest] {len(games)} completed MLB games found.\n')

    if not games:
        print('No completed games to backtest.')
        return

    print('[Backtest] Loading model data...')
    pitchers  = load_pitchers()
    hitters   = load_hitters()
    ballparks = load_ballparks()
    lineups   = load_lineups()
    team_rapg = fetch_team_rapg(season=date.today().year)
    print(f'[Backtest] RA/G data for {len(team_rapg)} teams.\n')

    old_correct = 0
    new_correct = 0
    both_correct = 0
    old_only = 0
    new_only = 0
    neither = 0
    total = 0
    skipped = 0

    # Per-tier breakdown for new model
    tier_stats = defaultdict(lambda: {'correct': 0, 'total': 0})

    for g in games:
        home     = g.get('homeTeam', '')
        away     = g.get('awayTeam', '')
        old_pick = g.get('pick', '')
        home_act = g.get('actualHomeScore')
        away_act = g.get('actualAwayScore')

        if not old_pick or home_act is None or away_act is None:
            skipped += 1
            continue
        if home_act == away_act:  # tie — skip
            skipped += 1
            continue

        actual_winner = home if home_act > away_act else away

        result = resimulate(g, pitchers, hitters, ballparks, lineups, team_rapg)
        if result is None:
            skipped += 1
            continue

        new_pick = result['new_pick']
        old_ok = (old_pick == actual_winner)
        new_ok = (new_pick == actual_winner)

        total += 1
        if old_ok: old_correct += 1
        if new_ok: new_correct += 1
        if old_ok and new_ok:     both_correct += 1
        elif old_ok and not new_ok: old_only += 1
        elif new_ok and not old_ok: new_only += 1
        else:                       neither += 1

        conf = g.get('confidence', 'Unknown') or 'Unknown'
        tier_stats[conf]['total'] += 1
        if new_ok:
            tier_stats[conf]['correct'] += 1

    print('=' * 60)
    print('MLB BACKTEST: OLD MODEL vs NEW (BULLPEN-SCALED) MODEL')
    print('=' * 60)
    print(f'Games evaluated : {total}   (skipped: {skipped})')
    print()

    if total == 0:
        print('No games to compare.')
        return

    old_pct = old_correct / total * 100
    new_pct = new_correct / total * 100
    delta   = new_pct - old_pct

    print(f'Old model picks : {old_correct}/{total}  ({old_pct:.1f}%)')
    print(f'New model picks : {new_correct}/{total}  ({new_pct:.1f}%)  [{delta:+.1f}pp]')
    print()
    print(f'Both right      : {both_correct}')
    print(f'Old only right  : {old_only}')
    print(f'New only right  : {new_only}')
    print(f'Neither right   : {neither}')
    print()

    print('NEW MODEL by confidence tier (from stored Firestore tier):')
    for tier in ['Elite', 'Strong', 'Unknown']:
        d = tier_stats.get(tier)
        if d and d['total'] >= 3:
            acc = d['correct'] / d['total'] * 100
            print(f'  {tier:10s}  {d["correct"]}/{d["total"]}  ({acc:.1f}%)')
    print('=' * 60)

    if team_rapg:
        print('\nTop 5 best bullpens (lowest RA/G):')
        for team, ra in sorted(team_rapg.items(), key=lambda x: x[1])[:5]:
            print(f'  {team}: {ra} RA/G')
        print('\nTop 5 worst bullpens (highest RA/G):')
        for team, ra in sorted(team_rapg.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f'  {team}: {ra} RA/G')


if __name__ == '__main__':
    main()
