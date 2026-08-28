"""
Send a daily morning email covering all active sports:
  - Soccer: yesterday's results + today's upcoming picks (soccer-today.json)
  - MLB:    yesterday's top picks vs actual results (top-picks.json + statsapi)
  - NFL:    this week's top picks if nfl-picks.json exists and has entries

Runs from the soccer workflow at 8 AM UTC.

Requires:
  GMAIL_USER         — sender Gmail address
  GMAIL_APP_PASSWORD — Gmail app password (Settings > Security > App passwords)
  EMAIL_TO           — recipient; defaults to GMAIL_USER
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ASSETS               = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
TODAY_PATH           = os.path.join(ASSETS, 'soccer-today.json')
PICKS_PATH           = os.path.join(ASSETS, 'top-picks.json')
YESTERDAY_PICKS_PATH = os.path.join(ASSETS, 'top-picks-yesterday.json')
NFL_PATH             = os.path.join(ASSETS, 'nfl-picks.json')

GMAIL_USER  = os.environ.get('GMAIL_USER', '')
GMAIL_PASS  = os.environ.get('GMAIL_APP_PASSWORD', '')
EMAIL_TO    = os.environ.get('EMAIL_TO', GMAIL_USER)

SOCCER_URL  = 'https://jesimon4-scoreboard.web.app/soccer-scoreboard'
MLB_URL     = 'https://jesimon4-scoreboard.web.app/scoreboard'


# ── Helpers ───────────────────────────────────────────────────────────────────

def pick_correct_soccer(pred_home, pred_away, act_home, act_away):
    if act_home is None or act_away is None:
        return None
    return ('home' if pred_home > pred_away else 'away') == \
           ('home' if act_home  > act_away  else 'away')


def pick_correct_mlb(pick_team, away_team, home_team, away_score, home_score):
    if away_score is None or home_score is None:
        return None
    actual_winner = home_team if home_score > away_score else away_team
    return pick_team == actual_winner


def summary_color(pct: int) -> str:
    if pct >= 55: return '#28a745'
    if pct < 45:  return '#dc3545'
    return '#856404'


TABLE_HEADER_STYLE = 'background:#1a1a2e;color:white'
TD = 'padding:8px;border-bottom:1px solid #ddd'


# ── Soccer section ────────────────────────────────────────────────────────────

SOCCER_SPORTS = ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1']


def fetch_soccer_from_firestore(yesterday: str) -> list:
    """Return yesterday's soccer game docs from Firestore with original predicted scores."""
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        print('[Email] FIREBASE_SERVICE_ACCOUNT not set — skipping Firestore soccer fetch.')
        return []
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
        cred = credentials.Certificate(json.loads(sa_json))
        app  = firebase_admin.initialize_app(cred, name='email_soccer')
        db   = fb_firestore.client(app)
        docs = db.collection('games').where('sport', 'in', SOCCER_SPORTS).stream()
        games = []
        for d in docs:
            data = d.to_dict()
            if data.get('gameDate') == yesterday and data.get('actualHomeScore') is not None:
                data.setdefault('league', data.get('sport', ''))
                games.append(data)
        firebase_admin.delete_app(app)
        games.sort(key=lambda g: g.get('gameTime', g.get('gameDate', '')))
        print(f'[Email] Firestore soccer: {len(games)} finished games for {yesterday}')
        return games
    except Exception as exc:
        print(f'[Email] Firestore soccer fetch error: {exc}')
        return []


def build_soccer_section(data: dict, yesterday: str, today_str: str,
                          firestore_results: list | None = None) -> str:
    # Use Firestore results (original predicted scores) when available; fall back to json
    if firestore_results is not None:
        results = firestore_results
    else:
        results = [r for r in data.get('recentResults', []) if r.get('gameDate') == yesterday]
        results.sort(key=lambda x: x.get('gameTime', ''))
    correct  = sum(1 for r in results
                   if pick_correct_soccer(r['predictedHomeScore'], r['predictedAwayScore'],
                                          r.get('actualHomeScore'), r.get('actualAwayScore')) is True)
    total    = len(results)

    upcoming = [u for u in data.get('upcoming', []) if u.get('gameDate') == today_str]
    upcoming.sort(key=lambda x: abs(x.get('homeWinProb', 0.5) - 0.5), reverse=True)
    top_picks = upcoming[:8]

    # Results table
    rows = ''
    for r in results:
        h_pred, a_pred = r['predictedHomeScore'], r['predictedAwayScore']
        h_act,  a_act  = r.get('actualHomeScore'), r.get('actualAwayScore')
        ok  = pick_correct_soccer(h_pred, a_pred, h_act, a_act)
        bg  = '#d4edda' if ok else '#f8d7da'
        rows += f"""
        <tr style="background:{bg}">
          <td style="{TD}">{r.get('league','')}</td>
          <td style="{TD}">{r.get('awayTeam','')} @ {r.get('homeTeam','')}</td>
          <td style="{TD};text-align:center">{a_pred:.1f}–{h_pred:.1f}</td>
          <td style="{TD};text-align:center;font-weight:bold">{a_act}–{h_act}</td>
          <td style="{TD};text-align:center">{'✅' if ok else '❌'}</td>
        </tr>"""

    if total:
        pct = round(correct / total * 100)
        results_html = f"""
        <p style="font-size:17px;font-weight:bold;color:{summary_color(pct)}">{correct}/{total} correct ({pct}%)</p>
        <table style="border-collapse:collapse;width:100%;font-size:14px">
          <thead><tr style="{TABLE_HEADER_STYLE}">
            <th style="padding:8px;text-align:left">League</th>
            <th style="padding:8px;text-align:left">Match</th>
            <th style="padding:8px;text-align:center">Predicted</th>
            <th style="padding:8px;text-align:center">Actual</th>
            <th style="padding:8px"></th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        results_html = '<p style="color:#666">No games tracked yesterday.</p>'

    # Today's picks
    pick_rows = ''
    for u in top_picks:
        wp       = u.get('homeWinProb', 0.5)
        home_fav = wp >= 0.5
        fav      = u['homeTeam'] if home_fav else u['awayTeam']
        und      = u['awayTeam'] if home_fav else u['homeTeam']
        fav_pct  = round(wp * 100) if home_fav else round((1 - wp) * 100)
        kickoff  = u.get('gameTime', '')[:16].replace('T', ' ') + ' UTC'
        cc       = '#28a745' if fav_pct >= 65 else ('#856404' if fav_pct >= 55 else '#6c757d')
        h_pred   = u.get('predictedHomeScore', 0)
        a_pred   = u.get('predictedAwayScore', 0)
        pred_str = f'{a_pred:.2f}–{h_pred:.2f}' if h_pred or a_pred else '—'
        pick_rows += f"""
        <tr>
          <td style="{TD}">{u.get('league','')}</td>
          <td style="{TD}">{u.get('awayTeam','')} @ {u.get('homeTeam','')}</td>
          <td style="{TD};color:#666;font-size:13px">{kickoff}</td>
          <td style="{TD};text-align:center;color:#555;font-size:13px">{pred_str}</td>
          <td style="{TD};font-weight:bold;color:{cc}">{fav} ({fav_pct}%)</td>
        </tr>"""

    if top_picks:
        picks_html = f"""
        <table style="border-collapse:collapse;width:100%;font-size:14px">
          <thead><tr style="{TABLE_HEADER_STYLE}">
            <th style="padding:8px;text-align:left">League</th>
            <th style="padding:8px;text-align:left">Match</th>
            <th style="padding:8px;text-align:left">Kickoff</th>
            <th style="padding:8px;text-align:center">Predicted</th>
            <th style="padding:8px;text-align:left">Model Pick</th>
          </tr></thead>
          <tbody>{pick_rows}</tbody>
        </table>"""
    else:
        picks_html = '<p style="color:#666">No upcoming matches today.</p>'

    return f"""
    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px">
      ⚽ Soccer &nbsp;<span style="font-size:14px;color:#666">Yesterday ({yesterday})</span>
    </h3>
    {results_html}
    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px;margin-top:24px">
      ⚽ Soccer Top Picks &nbsp;<span style="font-size:14px;color:#666">Today ({today_str})</span>
    </h3>
    {picks_html}"""


# ── MLB section ───────────────────────────────────────────────────────────────

def fetch_mlb_from_firestore(yesterday: str) -> list:
    """Return all MLB game docs from Firestore whose gameTime falls on `yesterday` (YYYY-MM-DD)."""
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        print('[Email] FIREBASE_SERVICE_ACCOUNT not set — skipping Firestore MLB fetch.')
        return []
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_firestore
        cred = credentials.Certificate(json.loads(sa_json))
        app  = firebase_admin.initialize_app(cred, name='email_mlb')
        db   = fb_firestore.client(app)
        docs = db.collection('games').where('sport', '==', 'MLB').stream()
        games = [d.to_dict() for d in docs if d.to_dict().get('gameTime', '')[:10] == yesterday]
        firebase_admin.delete_app(app)
        print(f'[Email] Firestore: {len(games)} MLB games for {yesterday}')
        return games
    except Exception as exc:
        print(f'[Email] Firestore MLB fetch error: {exc}')
        return []


def build_mlb_section_firestore(games: list, yesterday: str) -> str:
    if not games:
        return ''

    games.sort(key=lambda g: g.get('gameTime', ''))

    rows    = ''
    correct = 0
    total   = 0
    for g in games:
        away      = g.get('awayTeam', '')
        home      = g.get('homeTeam', '')
        pick      = g.get('pick', '')
        h_pred    = g.get('predictedHomeScore', 0)
        a_pred    = g.get('predictedAwayScore', 0)
        pred_str  = f'{a_pred:.2f}–{h_pred:.2f}'
        h_act     = g.get('actualHomeScore')
        a_act     = g.get('actualAwayScore')

        if h_act is not None and a_act is not None:
            ok         = pick_correct_mlb(pick, away, home, a_act, h_act)
            actual_str = f'{a_act}–{h_act}'
            icon       = '✅' if ok else '❌'
            bg         = '#d4edda' if ok else '#f8d7da'
            if ok is not None:
                total += 1
                if ok: correct += 1
        else:
            ok, actual_str, icon, bg = None, 'Pending', '⏳', '#fff'

        rows += f"""
        <tr style="background:{bg}">
          <td style="{TD}">{away} @ {home}</td>
          <td style="{TD};font-weight:bold">{pick}</td>
          <td style="{TD};font-size:12px;color:#555">{pred_str}</td>
          <td style="{TD};text-align:center">{actual_str}</td>
          <td style="{TD};text-align:center">{icon}</td>
        </tr>"""

    if total:
        pct     = round(correct / total * 100)
        summary = f'<p style="font-size:17px;font-weight:bold;color:{summary_color(pct)}">{correct}/{total} correct ({pct}%)</p>'
    else:
        summary = ''

    return f"""
    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px;margin-top:24px">
      ⚾ MLB &nbsp;<span style="font-size:14px;color:#666">Yesterday ({yesterday})</span>
    </h3>
    {summary}
    <table style="border-collapse:collapse;width:100%;font-size:14px">
      <thead><tr style="{TABLE_HEADER_STYLE}">
        <th style="padding:8px;text-align:left">Matchup</th>
        <th style="padding:8px;text-align:left">Pick</th>
        <th style="padding:8px;text-align:left">Predicted</th>
        <th style="padding:8px;text-align:center">Actual</th>
        <th style="padding:8px"></th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def fetch_mlb_actuals(yesterday_dt: datetime) -> dict:
    """Return {(away_name, home_name): (away_score, home_score)} for finished games."""
    try:
        import statsapi
        date_str = yesterday_dt.strftime('%m/%d/%Y')
        games    = statsapi.schedule(date=date_str)
        result   = {}
        for g in games:
            if g.get('status') == 'Final':
                result[(g['away_name'], g['home_name'])] = (g['away_score'], g['home_score'])
        return result
    except Exception as exc:
        print(f'[Email] MLB statsapi error: {exc}')
        return {}


def build_mlb_section_with_actuals(picks: list, yesterday: str, actuals: dict) -> str:
    """Build MLB email section using pre-fetched actuals dict.
    `picks` should already be yesterday's archived picks — no date filtering needed."""
    if not picks:
        return ''
    return _render_mlb_section(picks, yesterday, actuals)


def build_mlb_section(picks: list, yesterday: str, yesterday_dt: datetime) -> str:
    if not picks:
        return ''

    # Filter to yesterday's games (gameTime date matches yesterday)
    yesterday_picks = [p for p in picks if p.get('gameTime', '')[:10] == yesterday]
    if not yesterday_picks:
        # If no date match, just show all picks as "today's upcoming"
        yesterday_picks = picks

    actuals = fetch_mlb_actuals(yesterday_dt)
    return _render_mlb_section(yesterday_picks, yesterday, actuals)


def _render_mlb_section(yesterday_picks: list, yesterday: str, actuals: dict) -> str:

    rows    = ''
    correct = 0
    total   = 0
    for p in yesterday_picks:
        away     = p.get('awayTeam', '')
        home     = p.get('homeTeam', '')
        pick     = p.get('pick', '')
        pred_str = p.get('predictedScore', '')
        conf     = p.get('confidence', '')
        wp_pct   = round(p.get('winProb', 0) * 100)

        act = actuals.get((away, home))
        if act:
            a_score, h_score = act
            ok = pick_correct_mlb(pick, away, home, a_score, h_score)
            actual_str = f'{a_score}–{h_score}'
            icon = '✅' if ok else '❌'
            bg   = '#d4edda' if ok else '#f8d7da'
            if ok is not None:
                total += 1
                if ok: correct += 1
        else:
            ok, a_score, h_score = None, None, None
            actual_str = 'Pending'
            icon = '⏳'
            bg   = '#fff'

        rows += f"""
        <tr style="background:{bg}">
          <td style="{TD}">{away} @ {home}</td>
          <td style="{TD};font-weight:bold">{pick}</td>
          <td style="{TD};font-size:12px;color:#555">{pred_str}</td>
          <td style="{TD};text-align:center">{actual_str}</td>
          <td style="{TD};text-align:center">{icon}</td>
        </tr>"""

    if total:
        pct = round(correct / total * 100)
        summary = f'<p style="font-size:17px;font-weight:bold;color:{summary_color(pct)}">{correct}/{total} correct ({pct}%)</p>'
    else:
        summary = ''

    return f"""
    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px;margin-top:24px">
      ⚾ MLB &nbsp;<span style="font-size:14px;color:#666">Yesterday ({yesterday})</span>
    </h3>
    {summary}
    <table style="border-collapse:collapse;width:100%;font-size:14px">
      <thead><tr style="{TABLE_HEADER_STYLE}">
        <th style="padding:8px;text-align:left">Matchup</th>
        <th style="padding:8px;text-align:left">Pick</th>
        <th style="padding:8px;text-align:left">Predicted Score</th>
        <th style="padding:8px;text-align:center">Actual</th>
        <th style="padding:8px"></th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


# ── NFL section ───────────────────────────────────────────────────────────────

def build_nfl_section(picks: list) -> str:
    if not picks:
        return ''

    top  = picks[:6]
    rows = ''
    for p in top:
        home = p['homeTeam']
        away = p['awayTeam']
        pick = p['pick']
        wp   = round(p['winProb'] * 100)
        h_sc = p['homePredicted']
        a_sc = p['awayPredicted']
        conf = p.get('confidence', '')
        cc   = '#28a745' if wp >= 70 else ('#856404' if wp >= 60 else '#6c757d')
        rows += f"""
        <tr>
          <td style="{TD}">{away} @ {home}</td>
          <td style="{TD};font-weight:bold;color:{cc}">{pick} ({wp}%)</td>
          <td style="{TD};text-align:center;color:#555">{a_sc}–{h_sc}</td>
          <td style="{TD};text-align:center;font-size:12px">{conf}</td>
        </tr>"""

    return f"""
    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px;margin-top:24px">
      🏈 NFL Top Picks &nbsp;<span style="font-size:14px;color:#666">This Week</span>
    </h3>
    <table style="border-collapse:collapse;width:100%;font-size:14px">
      <thead><tr style="{TABLE_HEADER_STYLE}">
        <th style="padding:8px;text-align:left">Matchup</th>
        <th style="padding:8px;text-align:left">Pick</th>
        <th style="padding:8px;text-align:center">Predicted Score</th>
        <th style="padding:8px;text-align:center">Confidence</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


# ── Tweet drafts ─────────────────────────────────────────────────────────────

LEAGUE_FLAG = {
    'Premier League': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    'La Liga':        '🇪🇸',
    'Serie A':        '🇮🇹',
    'Bundesliga':     '🇩🇪',
    'Ligue 1':        '🇫🇷',
}
CONF_EMOJI = {'Elite': '🔥', 'Strong': '💪', 'Lean': '📊'}

TWEET_BOX = (
    'background:#f8f9fa;border:1px solid #dee2e6;border-left:4px solid #1a1a2e;'
    'border-radius:4px;padding:14px 16px;font-family:"Courier New",monospace;'
    'font-size:13px;white-space:pre-wrap;line-height:1.6;margin-bottom:16px;color:#1a1a2e'
)


def _tweet_box(label: str, text: str) -> str:
    char_count = len(text)
    return f"""
    <p style="margin:8px 0 4px;font-weight:bold;font-size:13px;color:#555">{label} &nbsp;<span style="font-weight:normal;color:#aaa">{char_count}/280 chars</span></p>
    <div style="{TWEET_BOX}">{text}</div>"""


def build_tweet_drafts(
    soccer_data: dict | None,
    mlb_picks: list | None,
    mlb_actuals: dict,
    nfl_picks: list | None,
    yesterday: str,
    today_str: str,
    mlb_yest_games: list | None = None,
) -> str:
    now      = datetime.now(timezone.utc)
    date_lbl = now.strftime('%b %-d').replace(' 0', ' ')
    drafts   = []

    # ── Soccer tweet ─────────────────────────────────────────────────────────
    if soccer_data:
        results  = [r for r in soccer_data.get('recentResults', []) if r.get('gameDate') == yesterday]
        correct  = sum(1 for r in results
                       if pick_correct_soccer(r['predictedHomeScore'], r['predictedAwayScore'],
                                              r.get('actualHomeScore'), r.get('actualAwayScore')) is True)
        total    = len(results)

        upcoming = [u for u in soccer_data.get('upcoming', []) if u.get('gameDate') == today_str]
        upcoming.sort(key=lambda x: abs(x.get('homeWinProb', 0.5) - 0.5), reverse=True)
        top3     = upcoming[:4]

        lines = [f'⚽ Soccer — {date_lbl}', '']
        if total:
            pct = round(correct / total * 100)
            lines.append(f'Yesterday: {correct}/{total} ({pct}%) {"✅" if pct >= 55 else "❌"}')
            lines.append('')
        if top3:
            lines.append("Today's picks:")
            for u in top3:
                wp       = u.get('homeWinProb', 0.5)
                home_fav = wp >= 0.5
                fav      = u['homeTeam'] if home_fav else u['awayTeam']
                und      = u['awayTeam'] if home_fav else u['homeTeam']
                fav_pct  = round(wp * 100) if home_fav else round((1 - wp) * 100)
                flag     = LEAGUE_FLAG.get(u.get('league', ''), '⚽')
                h_pred   = u.get('predictedHomeScore', 0)
                a_pred   = u.get('predictedAwayScore', 0)
                # show as Away-Home so it reads left team first
                pred_str = f' ({a_pred:.2f}-{h_pred:.2f})' if h_pred or a_pred else ''
                lines.append(f'{flag} {fav} ({fav_pct}%){pred_str}')
            lines.append('')
        lines.append(f'Full model 👉 {SOCCER_URL}')
        lines.append('#Soccer #SoccerPicks #EPL #LaLiga')
        drafts.append(_tweet_box('⚽ Soccer — post anytime today', '\n'.join(lines)))

    # ── MLB tweet ────────────────────────────────────────────────────────────
    if mlb_picks or mlb_yest_games:
        # Morning recap — use Firestore games (have actuals embedded) when available
        mlb_correct = mlb_total = 0
        hit_lines   = []
        recap_source = mlb_yest_games or []
        for g in recap_source:
            pick  = g.get('pick', '')
            if not pick:
                continue
            away, home = g.get('awayTeam', ''), g.get('homeTeam', '')
            h_act = g.get('actualHomeScore')
            a_act = g.get('actualAwayScore')
            if h_act is not None and a_act is not None:
                ok = pick_correct_mlb(pick, away, home, a_act, h_act)
                if ok is not None:
                    mlb_total += 1
                    if ok:
                        mlb_correct += 1
                        odds = g.get('odds', '')
                        hit_lines.append(f'✅ {pick} ML {odds}')
        # Fallback: use actuals dict when no Firestore games
        if not recap_source and mlb_picks:
            for p in mlb_picks:
                away, home = p.get('awayTeam', ''), p.get('homeTeam', '')
                pick = p.get('pick', '')
                act  = mlb_actuals.get((away, home))
                if act:
                    ok = pick_correct_mlb(pick, away, home, act[0], act[1])
                    if ok is not None:
                        mlb_total += 1
                        if ok:
                            mlb_correct += 1
                            odds = p.get('odds', '')
                            hit_lines.append(f'✅ {pick} ML {odds}')

        lines = [f'⚾ MLB Model — {date_lbl}', '']
        if mlb_total:
            pct = round(mlb_correct / mlb_total * 100)
            lines.append(f'Yesterday: {mlb_correct}/{mlb_total} ({pct}%) {"✅" if pct >= 55 else "❌"}')
            if hit_lines:
                lines.append('')
                lines.extend(hit_lines[:3])
        lines.append('')
        lines.append(f"Today's picks drop ~3 PM ET 👇")
        lines.append(f'Full model + player props 👉 {MLB_URL}')
        lines.append('#MLB #BaseballPicks #SportsBetting')
        drafts.append(_tweet_box('⚾ MLB — post in the morning', '\n'.join(lines)))

        # Second MLB draft: today's picks (to post at ~3 PM after picks refresh)
        top_picks = sorted(mlb_picks, key=lambda p: p.get('rank', 99))[:5]
        lines2 = [f'⚾ MLB Picks — {date_lbl}', '']
        for p in top_picks:
            emoji    = CONF_EMOJI.get(p.get('confidence', ''), '📊')
            team     = p.get('pick', '')
            odds     = p.get('odds', '')
            wp       = round(p.get('winProb', 0) * 100)
            opp      = p.get('awayTeam') if p.get('homeTeam') == team else p.get('homeTeam')
            pred_raw = p.get('predictedScore', '')
            pred_str = f' · {pred_raw}' if pred_raw else ''
            lines2.append(f'{emoji} {team} ML ({odds}) vs {opp} — {wp}%{pred_str}')
        lines2.append('')
        lines2.append(f'Full model + props 👉 {MLB_URL}')
        lines2.append('#MLB #BaseballPicks')
        drafts.append(_tweet_box('⚾ MLB — post at ~3 PM ET when today\'s picks are fresh', '\n'.join(lines2)))

    # ── NFL tweet ────────────────────────────────────────────────────────────
    if nfl_picks:
        top  = nfl_picks[:5]
        lines = [f'🏈 NFL Picks — {date_lbl}', '']
        for p in top:
            emoji = CONF_EMOJI.get(p.get('confidence', ''), '📊')
            pick  = p['pick']
            opp   = p['awayTeam'] if p['homeTeam'] == pick else p['homeTeam']
            wp    = round(p['winProb'] * 100)
            lines.append(f'{emoji} {pick} vs {opp} — {wp}%')
        lines.append('')
        lines.append(f'Full picks 👉 {MLB_URL}')
        lines.append('#NFL #NFLPicks #SportsBetting')
        drafts.append(_tweet_box('🏈 NFL — post Thursday or Sunday morning', '\n'.join(lines)))

    if not drafts:
        return ''

    return f"""
    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px;margin-top:32px">
      📋 Ready-to-Post Tweets
    </h3>
    <p style="color:#555;font-size:13px;margin-top:0">Copy and paste — each box is one tweet. Edit as you like before posting.</p>
    {''.join(drafts)}"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not GMAIL_USER or not GMAIL_PASS:
        print('[Email] GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping.')
        sys.exit(0)

    now          = datetime.now(timezone.utc)
    yesterday_dt = now - timedelta(days=1)
    yesterday    = yesterday_dt.strftime('%Y-%m-%d')
    today_str    = now.strftime('%Y-%m-%d')
    date_hdr     = now.strftime('%A, %B %d, %Y').replace(' 0', ' ')

    sections          = []
    soccer_data       = None
    mlb_picks_yest    = None   # yesterday's picks — used for results section
    mlb_picks_today   = None   # today's picks — used for tweet drafts
    mlb_actuals       = {}
    nfl_picks         = None

    # Soccer
    if os.path.exists(TODAY_PATH):
        with open(TODAY_PATH, encoding='utf-8') as f:
            soccer_data = json.load(f)
        soccer_fs = fetch_soccer_from_firestore(yesterday)
        sections.append(build_soccer_section(soccer_data, yesterday, today_str,
                                              firestore_results=soccer_fs if soccer_fs else None))
    else:
        print('[Email] soccer-today.json not found — skipping soccer section.')

    # MLB results — pull from Firestore (has every game + accurate predicted scores)
    mlb_fs_games = fetch_mlb_from_firestore(yesterday)
    if mlb_fs_games:
        mlb_html = build_mlb_section_firestore(mlb_fs_games, yesterday)
        if mlb_html:
            sections.append(mlb_html)
        # Build actuals dict for the tweet morning recap (yesterday W/L record)
        for g in mlb_fs_games:
            h_act = g.get('actualHomeScore')
            a_act = g.get('actualAwayScore')
            if h_act is not None and a_act is not None:
                mlb_actuals[(g.get('awayTeam', ''), g.get('homeTeam', ''))] = (a_act, h_act)
        mlb_picks_yest = mlb_fs_games  # expose for tweet draft morning recap
    else:
        # Fallback to archived file if Firestore unavailable
        print('[Email] Firestore returned no games — falling back to top-picks-yesterday.json')
        src = YESTERDAY_PICKS_PATH if os.path.exists(YESTERDAY_PICKS_PATH) else PICKS_PATH
        if os.path.exists(src):
            with open(src, encoding='utf-8') as f:
                mlb_picks_yest = json.load(f)
            mlb_actuals = fetch_mlb_actuals(yesterday_dt)
            mlb_html = build_mlb_section_with_actuals(mlb_picks_yest, yesterday, mlb_actuals)
            if mlb_html:
                sections.append(mlb_html)

    # Today's picks for tweet draft
    if os.path.exists(PICKS_PATH):
        with open(PICKS_PATH, encoding='utf-8') as f:
            mlb_picks_today = json.load(f)

    # NFL
    if os.path.exists(NFL_PATH):
        with open(NFL_PATH, encoding='utf-8') as f:
            nfl_picks = json.load(f)
        nfl_html = build_nfl_section(nfl_picks)
        if nfl_html:
            sections.append(nfl_html)

    if not sections:
        print('[Email] No data available — skipping.')
        sys.exit(0)

    # Tweet drafts — afternoon box uses today's picks; morning recap uses Firestore games
    tweet_html = build_tweet_drafts(
        soccer_data, mlb_picks_today, mlb_actuals, nfl_picks,
        yesterday, today_str,
        mlb_yest_games=mlb_fs_games if mlb_fs_games else None,
    )

    body = '\n<br>\n'.join(sections)
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:20px;color:#222">
  <div style="background:#1a1a2e;color:white;padding:16px 20px;border-radius:8px 8px 0 0">
    <h2 style="margin:0">🏆 Jack's Models — Daily Report</h2>
    <p style="margin:4px 0 0;opacity:0.7;font-size:14px">{date_hdr}</p>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px">
    {body}
    {tweet_html}
    <br>
    <p style="color:#aaa;font-size:12px;margin-top:24px">
      Generated automatically · Jack's Models
    </p>
  </div>
</body>
</html>"""

    subject = f"🏆 Jack's Models Daily Report — {yesterday}"
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = GMAIL_USER
    msg['To']      = EMAIL_TO
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())

    print(f'[Email] Sent "{subject}" to {EMAIL_TO}')


if __name__ == '__main__':
    main()
