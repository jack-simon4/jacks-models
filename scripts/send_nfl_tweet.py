"""
Post this week's top NFL picks as a tweet.
Called from the NFL workflow (Mon/Tue/Thu) after generate_nfl_picks.py runs.

Requires:
  TWITTER_API_KEY, TWITTER_API_SECRET,
  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
"""

import json
import os
import sys
from datetime import datetime, timezone

import tweepy

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
PICKS_PATH = os.path.join(ASSETS, 'nfl-picks.json')
APP_URL    = 'https://jesimon4-scoreboard.web.app/scoreboard'

API_KEY    = os.environ.get('TWITTER_API_KEY', '')
API_SECRET = os.environ.get('TWITTER_API_SECRET', '')
ACC_TOKEN  = os.environ.get('TWITTER_ACCESS_TOKEN', '')
ACC_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET', '')

CONF_EMOJI = {'Elite': '🔥', 'Strong': '💪', 'Lean': '📊'}


def build_tweet(picks: list) -> str:
    now      = datetime.now(timezone.utc)
    date_lbl = now.strftime('%b %-d').replace(' 0', ' ')

    top   = picks[:5]
    lines = []
    for p in top:
        emoji = CONF_EMOJI.get(p.get('confidence', ''), '📊')
        pick  = p['pick']
        opp   = p['awayTeam'] if p['homeTeam'] == pick else p['homeTeam']
        wp    = round(p['winProb'] * 100)
        lines.append(f'{emoji} {pick} vs {opp} — {wp}%')

    body  = '\n'.join(lines)
    tweet = (
        f'🏈 NFL Picks — {date_lbl}\n\n'
        f'{body}\n\n'
        f'Full model picks 👉 {APP_URL}\n'
        f'#NFL #NFLPicks #SportsBetting'
    )

    if len(tweet) > 280:
        body  = '\n'.join(lines[:4])
        tweet = (
            f'🏈 NFL Picks — {date_lbl}\n\n'
            f'{body}\n\n'
            f'Full picks 👉 {APP_URL}\n'
            f'#NFL #NFLPicks'
        )

    return tweet


def main():
    if not all([API_KEY, API_SECRET, ACC_TOKEN, ACC_SECRET]):
        print('[NFL Tweet] Twitter credentials not set — skipping.')
        sys.exit(0)

    if not os.path.exists(PICKS_PATH):
        print('[NFL Tweet] nfl-picks.json not found — skipping.')
        sys.exit(0)

    with open(PICKS_PATH, encoding='utf-8') as f:
        picks = json.load(f)

    if not picks:
        print('[NFL Tweet] No picks this week — skipping.')
        sys.exit(0)

    tweet = build_tweet(picks)
    print(f'[NFL Tweet] Posting:\n{tweet}\n')

    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACC_TOKEN,
        access_token_secret=ACC_SECRET,
    )
    try:
        resp = client.create_tweet(text=tweet)
        print(f'[NFL Tweet] Posted (id={resp.data["id"]})')
    except Exception as exc:
        print(f'[NFL Tweet] Failed: {exc}')


if __name__ == '__main__':
    main()
