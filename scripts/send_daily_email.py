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

ASSETS      = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
TODAY_PATH  = os.path.join(ASSETS, 'soccer-today.json')
PICKS_PATH  = os.path.join(ASSETS, 'top-picks.json')
NFL_PATH    = os.path.join(ASSETS, 'nfl-picks.json')

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

def build_soccer_section(data: dict, yesterday: str, today_str: str) -> str:
    results  = [r for r in data.get('recentResults', []) if r.get('gameDate') == yesterday]
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
        fav_pct  = round(wp * 100) if home_fav else round((1 - wp) * 100)
        kickoff  = u.get('gameTime', '')[:16].replace('T', ' ') + ' UTC'
        cc       = '#28a745' if fav_pct >= 65 else ('#856404' if fav_pct >= 55 else '#6c757d')
        pick_rows += f"""
        <tr>
          <td style="{TD}">{u.get('league','')}</td>
          <td style="{TD}">{u.get('awayTeam','')} @ {u.get('homeTeam','')}</td>
          <td style="{TD};color:#666;font-size:13px">{kickoff}</td>
          <td style="{TD};font-weight:bold;color:{cc}">{fav} ({fav_pct}%)</td>
        </tr>"""

    if top_picks:
        picks_html = f"""
        <table style="border-collapse:collapse;width:100%;font-size:14px">
          <thead><tr style="{TABLE_HEADER_STYLE}">
            <th style="padding:8px;text-align:left">League</th>
            <th style="padding:8px;text-align:left">Match</th>
            <th style="padding:8px;text-align:left">Kickoff</th>
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


def build_mlb_section(picks: list, yesterday: str, yesterday_dt: datetime) -> str:
    if not picks:
        return ''

    # Filter to yesterday's games (gameTime date matches yesterday)
    yesterday_picks = [p for p in picks if p.get('gameTime', '')[:10] == yesterday]
    if not yesterday_picks:
        # If no date match, just show all picks as "today's upcoming"
        yesterday_picks = picks

    actuals = fetch_mlb_actuals(yesterday_dt)

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

    sections = []

    # Soccer
    if os.path.exists(TODAY_PATH):
        with open(TODAY_PATH, encoding='utf-8') as f:
            soccer_data = json.load(f)
        sections.append(build_soccer_section(soccer_data, yesterday, today_str))
    else:
        print('[Email] soccer-today.json not found — skipping soccer section.')

    # MLB
    if os.path.exists(PICKS_PATH):
        with open(PICKS_PATH, encoding='utf-8') as f:
            mlb_picks = json.load(f)
        mlb_html = build_mlb_section(mlb_picks, yesterday, yesterday_dt)
        if mlb_html:
            sections.append(mlb_html)
    else:
        print('[Email] top-picks.json not found — skipping MLB section.')

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
