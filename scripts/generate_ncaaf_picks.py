"""
Generate NCAAF top picks for upcoming games and write ncaaf-picks.json.

Uses NCAAF-Stats.csv (built by fetch_ncaaf_stats.py) for team ratings
and the CFBD API for the upcoming game schedule.

Model is a direct Python port of the TypeScript NCAAF case in
ScoreboardComponent.runSimulation().

Output: src/assets/ncaaf-picks.json
"""

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone

import requests

API_KEY = os.environ.get('CFBD_API_KEY', '')
BASE    = 'https://api.collegefootballdata.com'
ASSETS  = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
STATS_PATH = os.path.join(ASSETS, 'NCAAF-Stats.csv')
OUTPUT     = os.path.join(ASSETS, 'ncaaf-picks.json')


def load_stats() -> dict:
    """Parse NCAAF-Stats.csv by column position (has duplicate 'Last 3' headers)."""
    stats = {}
    if not os.path.exists(STATS_PATH):
        print('[NCAAF] NCAAF-Stats.csv not found.')
        return stats
    with open(STATS_PATH, encoding='utf-8') as f:
        lines = f.read().strip().split('\n')
    for line in lines[1:]:
        parts = line.split(',')
        if len(parts) < 19:
            continue
        try:
            team = parts[0].strip()
            stats[team] = {
                'oRating':   float(parts[2]),
                'dRating':   float(parts[3]),
                'wYdsPlay':  float(parts[6]),
                'wdYdsPlay': float(parts[9]),
                'wYdsPt':    float(parts[12]),
                'wdYdsPt':   float(parts[15]),
                'PlaysGame': float(parts[16]),
                'dPlaysGame': float(parts[17]),
                'HomeAdv':   float(parts[18]),
            }
        except (ValueError, IndexError):
            pass
    print(f'[NCAAF] Loaded stats for {len(stats)} teams.')
    return stats


def simulate(home: dict, away: dict) -> tuple[float, float]:
    """Port of the TypeScript NCAAF model formula."""
    home_adv = home['HomeAdv'] / 2
    home_score = (
        (0.5 * home['wYdsPlay'] * away['dRating'] + 0.5 * away['wdYdsPlay'] * home['oRating'])
        * (home['PlaysGame'] * (away['dPlaysGame'] / 68))
        / ((away['wdYdsPt'] + home['wYdsPt']) / 2)
        + home_adv + 1.74
    )
    away_score = (
        (0.5 * away['wYdsPlay'] * home['dRating'] + 0.5 * home['wdYdsPlay'] * away['oRating'])
        * (away['PlaysGame'] * (home['dPlaysGame'] / 68))
        / ((home['wdYdsPt'] + away['wYdsPt']) / 2)
        - home_adv + 1.74
    )
    return round(home_score, 2), round(away_score, 2)


def win_prob(diff: float) -> float:
    # sigmoid on score margin; k=0.12 fits NCAAF scoring variance
    return round(1 / (1 + math.exp(-0.12 * diff)), 3)


def confidence_label(edge: float) -> str:
    if edge >= 0.18: return 'Elite'
    if edge >= 0.10: return 'Strong'
    if edge >= 0.05: return 'Lean'
    return ''


def fetch_schedule(year: int, weeks: list[int]) -> list:
    if not API_KEY:
        print('[NCAAF] CFBD_API_KEY not set — no schedule available.')
        return []
    headers = {'Authorization': f'Bearer {API_KEY}'}
    games   = []
    seen    = set()
    for week in weeks:
        for season_type in ('regular',):
            try:
                resp = requests.get(
                    f'{BASE}/games',
                    params={'year': year, 'week': week, 'seasonType': season_type},
                    headers=headers, timeout=15,
                )
                if resp.status_code == 200:
                    for g in resp.json():
                        gid = g.get('id')
                        if gid not in seen:
                            seen.add(gid)
                            games.append(g)
                time.sleep(0.3)
            except Exception as exc:
                print(f'[NCAAF] Schedule w{week} error: {exc}')
    print(f'[NCAAF] Fetched {len(games)} games for weeks {weeks}.')
    return games


def current_ncaaf_weeks(now: datetime) -> list[int]:
    """Return which CFBD week numbers to query based on today's date."""
    # Season starts late August. Week 0 = last Sat of Aug, Week 1 = first Sat of Sep.
    # Approximate: day-of-year calculation for NCAAF week.
    # Aug 24-30 → week 0; Aug 31-Sep 6 → week 1; etc.
    start_of_week0 = datetime(now.year, 8, 24, tzinfo=timezone.utc)
    days_in = max(0, (now - start_of_week0).days)
    current_week = days_in // 7
    return list(range(max(0, current_week), current_week + 2))  # this week + next


def generate_ncaaf_picks():
    stats = load_stats()
    if not stats:
        with open(OUTPUT, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return

    now        = datetime.now(timezone.utc)
    year       = now.year if now.month >= 8 else now.year - 1
    weeks      = current_ncaaf_weeks(now)
    games      = fetch_schedule(year, weeks)
    window_end = now + timedelta(days=7)

    picks   = []
    skipped = 0

    for g in games:
        if g.get('home_points') is not None:
            continue  # already played

        start_raw = g.get('start_date', '')
        try:
            game_dt = datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            skipped += 1
            continue

        if game_dt < now or game_dt > window_end:
            continue

        home = g.get('home_team', '')
        away = g.get('away_team', '')
        h_stats = stats.get(home)
        a_stats = stats.get(away)
        if not h_stats or not a_stats:
            print(f'  [Skip] {away} @ {home} — not in stats')
            skipped += 1
            continue

        h_score, a_score = simulate(h_stats, a_stats)
        diff  = h_score - a_score
        wp    = win_prob(diff)

        if wp >= 0.5:
            pick_team, pick_wp = home, wp
        else:
            pick_team, pick_wp = away, 1 - wp

        edge  = pick_wp - 0.5
        label = confidence_label(edge)
        if not label:
            continue

        picks.append({
            'homeTeam':      home,
            'awayTeam':      away,
            'homePredicted': h_score,
            'awayPredicted': a_score,
            'pick':          pick_team,
            'winProb':       round(pick_wp, 3),
            'confidence':    label,
            'gameTime':      start_raw,
        })

    picks.sort(key=lambda p: p['winProb'], reverse=True)
    for i, p in enumerate(picks):
        p['rank'] = i + 1

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(picks, f, indent=2)

    print(f'[NCAAF] {len(picks)} picks saved → {OUTPUT}  ({skipped} skipped)')


if __name__ == '__main__':
    generate_ncaaf_picks()
