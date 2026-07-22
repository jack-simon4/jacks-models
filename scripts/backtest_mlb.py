"""
Backtest MLB moneyline accuracy using completed games stored in Firestore.

Reads all MLB games where actualHomeScore is not null, determines whether
the model's pick was correct, and reports accuracy by confidence tier.

Usage:
    FIREBASE_SERVICE_ACCOUNT=<json> python scripts/backtest_mlb.py

Also accepts --min-games N to skip tiers with fewer than N samples.
"""

import argparse
import json
import os
import sys
from collections import defaultdict

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fb_firestore
except ImportError:
    print('[Backtest] firebase-admin not installed.')
    sys.exit(1)


def ml_to_implied_prob(ml_str: str) -> float | None:
    """Convert American moneyline string to implied probability (no vig)."""
    try:
        ml = int(str(ml_str).replace('+', ''))
        if ml > 0:
            return 100 / (ml + 100)
        else:
            return abs(ml) / (abs(ml) + 100)
    except (ValueError, TypeError):
        return None


def load_completed_games(db) -> list:
    docs = db.collection('games').where('sport', '==', 'MLB').stream()
    games = []
    for doc in docs:
        d = doc.to_dict()
        if d.get('actualHomeScore') is not None and d.get('actualAwayScore') is not None:
            games.append(d)
    return games


def evaluate(games: list, min_games: int):
    tiers = defaultdict(lambda: {'correct': 0, 'total': 0, 'roi_units': 0.0})
    overall = {'correct': 0, 'total': 0, 'roi_units': 0.0}
    consensus_stats = {'correct': 0, 'total': 0}  # games that had Vegas odds

    skipped = 0

    for g in games:
        pick     = g.get('pick', '')
        home     = g.get('homeTeam', '')
        away     = g.get('awayTeam', '')
        conf     = g.get('confidence', 'Unknown')
        home_act = g.get('actualHomeScore')
        away_act = g.get('actualAwayScore')
        ml_str   = g.get('odds', '')

        if not pick or home_act is None or away_act is None:
            skipped += 1
            continue

        actual_winner = home if home_act > away_act else away if away_act > home_act else None
        if actual_winner is None:
            skipped += 1
            continue

        correct = (pick == actual_winner)
        tiers[conf]['total'] += 1
        overall['total'] += 1
        if correct:
            tiers[conf]['correct'] += 1
            overall['correct'] += 1

        # ROI calculation: $100 flat-bet
        prob = ml_to_implied_prob(ml_str)
        if prob is not None:
            consensus_stats['total'] += 1
            if correct:
                consensus_stats['correct'] += 1
            # Profit/loss in units (1 unit = $100 bet)
            ml = int(str(ml_str).replace('+', ''))
            if correct:
                payout = 100 / abs(ml) if ml < 0 else ml / 100
                tiers[conf]['roi_units'] += payout
                overall['roi_units'] += payout
            else:
                tiers[conf]['roi_units'] -= 1.0
                overall['roi_units'] -= 1.0

    print('\n' + '=' * 60)
    print('MLB MONEYLINE BACKTEST RESULTS')
    print('=' * 60)
    print(f'Total completed games: {overall["total"]}  |  Skipped: {skipped}')
    print()

    order = ['Elite', 'Strong', 'Lean', 'Unknown']
    for tier in order:
        d = tiers.get(tier)
        if d is None or d['total'] < min_games:
            continue
        acc = d['correct'] / d['total'] * 100
        roi = d['roi_units'] / d['total'] * 100
        print(f'{tier:10s}  {d["correct"]:3d}/{d["total"]:3d}  accuracy={acc:.1f}%  ROI={roi:+.1f}%/bet')

    if overall['total'] > 0:
        acc = overall['correct'] / overall['total'] * 100
        roi = overall['roi_units'] / overall['total'] * 100
        print('-' * 60)
        print(f'{"OVERALL":10s}  {overall["correct"]:3d}/{overall["total"]:3d}  accuracy={acc:.1f}%  ROI={roi:+.1f}%/bet')

    print('=' * 60)

    # Edge calibration: break into 5% win-prob buckets
    print('\nWIN-PROB CALIBRATION (model predicted vs actual)')
    print(f'{"Bucket":20s}  {"Games":>6}  {"Pred%":>6}  {"Actual%":>7}')
    print('-' * 48)

    buckets = defaultdict(lambda: {'total': 0, 'correct': 0, 'wp_sum': 0.0})
    for g in games:
        wp   = g.get('winProb')
        pick = g.get('pick', '')
        home = g.get('homeTeam', '')
        home_act = g.get('actualHomeScore')
        away_act = g.get('actualAwayScore')
        if wp is None or not pick or home_act is None or away_act is None:
            continue
        actual_winner = home if home_act > away_act else (
            g.get('awayTeam', '') if away_act > home_act else None
        )
        if actual_winner is None:
            continue
        b = int(wp * 20) / 20  # round down to nearest 5%
        buckets[b]['total'] += 1
        buckets[b]['wp_sum'] += wp
        if pick == actual_winner:
            buckets[b]['correct'] += 1

    for b in sorted(buckets):
        d = buckets[b]
        if d['total'] < 3:
            continue
        pred_pct  = d['wp_sum'] / d['total'] * 100
        actual_pct = d['correct'] / d['total'] * 100
        label = f'{b*100:.0f}%–{(b+0.05)*100:.0f}%'
        print(f'{label:20s}  {d["total"]:6d}  {pred_pct:6.1f}%  {actual_pct:7.1f}%')

    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--min-games', type=int, default=5,
                        help='Minimum games in a tier to display it')
    args = parser.parse_args()

    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        print('[Backtest] FIREBASE_SERVICE_ACCOUNT not set.')
        sys.exit(1)

    cred = credentials.Certificate(json.loads(sa_json))
    app = firebase_admin.initialize_app(cred)
    db = fb_firestore.client()

    print('[Backtest] Loading completed games from Firestore...')
    games = load_completed_games(db)
    print(f'[Backtest] {len(games)} completed MLB games found.')

    firebase_admin.delete_app(app)

    evaluate(games, args.min_games)


if __name__ == '__main__':
    main()
