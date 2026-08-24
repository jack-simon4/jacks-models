"""
Post a daily tweet thread with today's top soccer picks + yesterday's record.

Thread structure:
  Tweet 1 — Yesterday's record + today's top picks (main tweet)
  Tweet 2+ — One tweet per league if there are enough picks to split out

Requires env vars (set as GitHub secrets):
  TWITTER_API_KEY            — API key (consumer key)
  TWITTER_API_SECRET         — API secret (consumer secret)
  TWITTER_ACCESS_TOKEN       — Access token
  TWITTER_ACCESS_TOKEN_SECRET — Access token secret
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import tweepy

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
TODAY_PATH = os.path.join(ASSETS, 'soccer-today.json')
APP_URL    = 'https://jesimon4-scoreboard.web.app/soccer-scoreboard'

API_KEY    = os.environ.get('TWITTER_API_KEY', '')
API_SECRET = os.environ.get('TWITTER_API_SECRET', '')
ACC_TOKEN  = os.environ.get('TWITTER_ACCESS_TOKEN', '')
ACC_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET', '')

LEAGUE_EMOJI = {
    'Premier League': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    'La Liga':        '🇪🇸',
    'Serie A':        '🇮🇹',
    'Bundesliga':     '🇩🇪',
    'Ligue 1':        '🇫🇷',
    'MLS':            '🇺🇸',
}


def pick_correct(pred_home, pred_away, act_home, act_away):
    if act_home is None or act_away is None:
        return None
    pred_winner = 'home' if pred_home > pred_away else 'away'
    act_winner  = 'home' if act_home  > act_away  else 'away'
    return pred_winner == act_winner


def build_tweets(data: dict) -> list[str]:
    now       = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    today_str = now.strftime('%Y-%m-%d')
    date_lbl  = now.strftime('%b %-d').replace(' 0', ' ')  # e.g. "Aug 24"

    # Yesterday's results summary
    results = [r for r in data.get('recentResults', []) if r.get('gameDate') == yesterday]
    correct = sum(
        1 for r in results
        if pick_correct(r['predictedHomeScore'], r['predictedAwayScore'],
                        r.get('actualHomeScore'), r.get('actualAwayScore')) is True
    )
    total = len(results)

    # Today's picks sorted by confidence, capped at 6 for the main tweet
    upcoming = [u for u in data.get('upcoming', []) if u.get('gameDate') == today_str]
    upcoming.sort(key=lambda x: abs(x.get('homeWinProb', 0.5) - 0.5), reverse=True)
    top_picks = upcoming[:6]

    if not top_picks:
        print('[Tweet] No upcoming picks for today — skipping.')
        return []

    # Build yesterday line
    if total:
        pct = round(correct / total * 100)
        yesterday_line = f'Yesterday: {correct}/{total} ({pct}%) ✅\n\n'
    else:
        yesterday_line = ''

    # Build pick lines
    pick_lines = []
    for u in top_picks:
        wp       = u.get('homeWinProb', 0.5)
        home_fav = wp >= 0.5
        fav_team = u['homeTeam'] if home_fav else u['awayTeam']
        fav_pct  = round(wp * 100) if home_fav else round((1 - wp) * 100)
        league   = u.get('league', '')
        emoji    = LEAGUE_EMOJI.get(league, '⚽')
        pick_lines.append(f'{emoji} {fav_team} ({fav_pct}%)')

    picks_block = '\n'.join(pick_lines)
    hashtags    = '#Soccer #SoccerPicks #FootballPredictions'

    main_tweet = (
        f"⚽ Today's Top Soccer Picks — {date_lbl}\n\n"
        f"{yesterday_line}"
        f"{picks_block}\n\n"
        f"Full picks + stats 👉 {APP_URL}\n"
        f"{hashtags}"
    )

    # If it somehow exceeds 280 chars, trim picks to 4
    if len(main_tweet) > 280:
        picks_block = '\n'.join(pick_lines[:4])
        main_tweet = (
            f"⚽ Today's Top Soccer Picks — {date_lbl}\n\n"
            f"{yesterday_line}"
            f"{picks_block}\n\n"
            f"Full picks 👉 {APP_URL}\n"
            f"{hashtags}"
        )

    return [main_tweet]


def post_tweets(tweets: list[str]):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACC_TOKEN,
        access_token_secret=ACC_SECRET,
    )

    reply_to = None
    for i, text in enumerate(tweets):
        if reply_to:
            resp = client.create_tweet(text=text, in_reply_to_tweet_id=reply_to)
        else:
            resp = client.create_tweet(text=text)
        reply_to = resp.data['id']
        print(f'[Tweet {i+1}] Posted (id={reply_to}): {text[:60]}...')


def main():
    if not all([API_KEY, API_SECRET, ACC_TOKEN, ACC_SECRET]):
        print('[Tweet] Twitter credentials not set — skipping.')
        sys.exit(0)

    if not os.path.exists(TODAY_PATH):
        print('[Tweet] soccer-today.json not found — skipping.')
        sys.exit(0)

    with open(TODAY_PATH, encoding='utf-8') as f:
        data = json.load(f)

    tweets = build_tweets(data)
    if tweets:
        post_tweets(tweets)


if __name__ == '__main__':
    main()
