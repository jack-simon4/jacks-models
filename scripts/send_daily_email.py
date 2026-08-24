"""
Send a daily soccer email with:
  - Yesterday's results (predicted vs actual, win/loss on each pick)
  - Today's top model picks sorted by confidence

Requires env vars:
  GMAIL_USER         — your Gmail address (sender)
  GMAIL_APP_PASSWORD — Gmail app password (not your regular password)
  EMAIL_TO           — recipient; defaults to GMAIL_USER if not set
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ASSETS     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
TODAY_PATH = os.path.join(ASSETS, 'soccer-today.json')

GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_PASS = os.environ.get('GMAIL_APP_PASSWORD', '')
EMAIL_TO   = os.environ.get('EMAIL_TO', GMAIL_USER)


def pick_correct(pred_home, pred_away, act_home, act_away):
    if act_home is None or act_away is None:
        return None
    pred_winner = 'home' if pred_home > pred_away else 'away'
    act_winner  = 'home' if act_home  > act_away  else 'away'
    return pred_winner == act_winner


def build_html(data: dict) -> str:
    now       = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    today_str = now.strftime('%Y-%m-%d')
    date_hdr  = now.strftime('%A, %B %d, %Y').replace(' 0', ' ')

    # Yesterday's finished results
    results = [r for r in data.get('recentResults', []) if r.get('gameDate') == yesterday]
    results.sort(key=lambda x: x.get('gameTime', ''))

    correct = sum(
        1 for r in results
        if pick_correct(r['predictedHomeScore'], r['predictedAwayScore'],
                        r.get('actualHomeScore'), r.get('actualAwayScore')) is True
    )
    total = len(results)

    # Today's upcoming picks, sorted by model confidence (distance from 50%)
    upcoming = [u for u in data.get('upcoming', []) if u.get('gameDate') == today_str]
    upcoming.sort(key=lambda x: abs(x.get('homeWinProb', 0.5) - 0.5), reverse=True)
    top_picks = upcoming[:8]

    # ── Results table rows ────────────────────────────────────────────────────
    rows_results = ''
    for r in results:
        h_pred = r['predictedHomeScore']
        a_pred = r['predictedAwayScore']
        h_act  = r.get('actualHomeScore')
        a_act  = r.get('actualAwayScore')
        ok     = pick_correct(h_pred, a_pred, h_act, a_act)
        icon   = '✅' if ok else '❌'
        bg     = '#d4edda' if ok else '#f8d7da'
        rows_results += f"""
        <tr style="background:{bg}">
          <td style="padding:8px;border-bottom:1px solid #ddd">{r.get('league','')}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd">{r.get('awayTeam','')} @ {r.get('homeTeam','')}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center">{a_pred:.1f}–{h_pred:.1f}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;font-weight:bold">{a_act}–{h_act}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center">{icon}</td>
        </tr>"""

    if not results:
        results_section = '<p style="color:#666">No games tracked yesterday.</p>'
    else:
        pct = round(correct / total * 100) if total else 0
        summary_color = '#28a745' if pct >= 55 else ('#dc3545' if pct < 45 else '#856404')
        results_section = f"""
        <p style="font-size:18px;font-weight:bold;color:{summary_color}">{correct}/{total} correct ({pct}%)</p>
        <table style="border-collapse:collapse;width:100%;font-size:14px">
          <thead>
            <tr style="background:#1a1a2e;color:white">
              <th style="padding:8px;text-align:left">League</th>
              <th style="padding:8px;text-align:left">Match</th>
              <th style="padding:8px;text-align:center">Predicted</th>
              <th style="padding:8px;text-align:center">Actual</th>
              <th style="padding:8px"></th>
            </tr>
          </thead>
          <tbody>{rows_results}</tbody>
        </table>"""

    # ── Picks table rows ──────────────────────────────────────────────────────
    rows_picks = ''
    for u in top_picks:
        wp        = u.get('homeWinProb', 0.5)
        home_fav  = wp >= 0.5
        fav_team  = u['homeTeam'] if home_fav else u['awayTeam']
        fav_pct   = round(wp * 100) if home_fav else round((1 - wp) * 100)
        kickoff   = u.get('gameTime', '')[:16].replace('T', ' ') + ' UTC'
        conf_color = '#28a745' if fav_pct >= 65 else ('#856404' if fav_pct >= 55 else '#6c757d')
        rows_picks += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #ddd">{u.get('league','')}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd">{u.get('awayTeam','')} @ {u.get('homeTeam','')}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;color:#666;font-size:13px">{kickoff}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;font-weight:bold;color:{conf_color}">{fav_team} ({fav_pct}%)</td>
        </tr>"""

    if not top_picks:
        picks_section = '<p style="color:#666">No upcoming matches found for today.</p>'
    else:
        picks_section = f"""
        <table style="border-collapse:collapse;width:100%;font-size:14px">
          <thead>
            <tr style="background:#1a1a2e;color:white">
              <th style="padding:8px;text-align:left">League</th>
              <th style="padding:8px;text-align:left">Match</th>
              <th style="padding:8px;text-align:left">Kickoff</th>
              <th style="padding:8px;text-align:left">Model Pick</th>
            </tr>
          </thead>
          <tbody>{rows_picks}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#222">
  <div style="background:#1a1a2e;color:white;padding:16px 20px;border-radius:8px 8px 0 0">
    <h2 style="margin:0">⚽ Jack's Models — Daily Soccer Report</h2>
    <p style="margin:4px 0 0;opacity:0.7;font-size:14px">{date_hdr}</p>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px">

    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px">
      Yesterday's Results &nbsp;<span style="font-size:14px;color:#666">({yesterday})</span>
    </h3>
    {results_section}

    <br>
    <h3 style="border-bottom:2px solid #1a1a2e;padding-bottom:6px">
      Today's Top Picks &nbsp;<span style="font-size:14px;color:#666">({today_str})</span>
    </h3>
    {picks_section}

    <br>
    <p style="color:#aaa;font-size:12px;margin-top:24px">
      Generated automatically by Jack's Models · Data from football-data.org
    </p>
  </div>
</body>
</html>"""


def main():
    if not GMAIL_USER or not GMAIL_PASS:
        print('[Email] GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping.')
        sys.exit(0)

    if not os.path.exists(TODAY_PATH):
        print('[Email] soccer-today.json not found — skipping.')
        sys.exit(0)

    with open(TODAY_PATH, encoding='utf-8') as f:
        data = json.load(f)

    now       = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    html      = build_html(data)
    subject   = f"⚽ Jack's Models — {yesterday} Soccer Results"

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
