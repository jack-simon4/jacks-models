"""
Post today's top MLB picks as a tweet.
Called from the MLB workflow right after generate_top_picks.py runs (~3 PM UTC).

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
PICKS_PATH = os.path.join(ASSETS, 'top-picks.json')
APP_URL    = 'https://jesimon4-scoreboard.web.app/scoreboard'

API_KEY    = os.environ.get('TWITTER_API_KEY', '')
API_SECRET = os.environ.get('TWITTER_API_SECRET', '')
ACC_TOKEN  = os.environ.get('TWITTER_ACCESS_TOKEN', '')
ACC_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET', '')

CONF_EMOJI = {'Elite': '🔥', 'Strong': '💪', 'Lean': '📊'}


def build_tweet(picks: list) -> str:
    now      = datetime.now(timezone.utc)
    date_lbl = now.strftime('%b %-d').replace(' 0', ' ')

    # Top 5 by rank
    top = sorted(picks, key=lambda p: p.get('rank', 99))[:5]

    lines = []
    for p in top:
        emoji  = CONF_EMOJI.get(p.get('confidence', ''), '📊')
        team   = p.get('pick', '')
        odds   = p.get('odds', '')
        wp     = round(p.get('winProb', 0) * 100)
        opp    = p.get('awayTeam') if p.get('homeTeam') == team else p.get('homeTeam')
        lines.append(f'{emoji} {team} ML ({odds}) vs {opp} — {wp}%')

    body = '\n'.join(lines)
    tweet = (
        f'⚾ Today\'s Top MLB Picks — {date_lbl}\n\n'
        f'{body}\n\n'
        f'Full model + props 👉 {APP_URL}\n'
        f'#MLB #BaseballPicks #SportsBetting'
    )

    if len(tweet) > 280:
        top = top[:4]
        body = '\n'.join(lines[:4])
        tweet = (
            f'⚾ Today\'s Top MLB Picks — {date_lbl}\n\n'
            f'{body}\n\n'
            f'Full picks 👉 {APP_URL}\n'
            f'#MLB #BaseballPicks'
        )

    return tweet


def main():
    if not all([API_KEY, API_SECRET, ACC_TOKEN, ACC_SECRET]):
        print('[MLB Tweet] Twitter credentials not set — skipping.')
        sys.exit(0)

    if not os.path.exists(PICKS_PATH):
        print('[MLB Tweet] top-picks.json not found — skipping.')
        sys.exit(0)

    with open(PICKS_PATH, encoding='utf-8') as f:
        picks = json.load(f)

    if not picks:
        print('[MLB Tweet] No picks today — skipping.')
        sys.exit(0)

    tweet = build_tweet(picks)
    print(f'[MLB Tweet] Posting:\n{tweet}\n')

    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACC_TOKEN,
        access_token_secret=ACC_SECRET,
    )
    try:
        resp = client.create_tweet(text=tweet)
        print(f'[MLB Tweet] Posted (id={resp.data["id"]})')
    except Exception as exc:
        print(f'[MLB Tweet] Failed: {exc}')


if __name__ == '__main__':
    main()
