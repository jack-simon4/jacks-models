"""
Generate PNG pick cards for social media (Instagram, Twitter, TikTok).

Outputs two files per run:
  src/assets/social-picks.png  — 1080x1080 square card (Instagram/Twitter)
  src/assets/social-picks-story.png — 1080x1920 vertical card (Stories/Reels/TikTok)

These can be downloaded and posted as-is, or embedded in the daily email.

Requires: pillow  (pip install pillow)
"""

import json
import math
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
ET     = ZoneInfo('America/New_York')

# ── Colors ────────────────────────────────────────────────────────────────────
BG_DARK    = (15, 15, 30)       # near-black navy
BG_CARD    = (30, 32, 52)       # card background
ACCENT     = (0, 255, 149)      # green accent (#00ff95)
ORANGE     = (245, 166, 35)     # amber for spread edge (#f5a623)
WHITE      = (255, 255, 255)
GREY       = (170, 170, 190)
GOLD       = (255, 215, 0)
RED        = (231, 76, 60)
GREEN_DIM  = (46, 204, 113)

SPORT_COLORS = {
    'NFL':    ((92, 26, 26),   (245, 166, 35)),
    'NBA':    ((92, 58, 26),   (245, 209, 35)),
    'NHL':    ((26, 58, 92),   (160, 200, 245)),
    'NCAAF':  ((61, 26, 92),   (201, 127, 245)),
    'NCAAM':  ((26, 74, 46),   (126, 245, 160)),
    'MLB':    ((26, 58, 92),   (126, 200, 227)),
    'Soccer': ((26, 92, 42),   (126, 245, 160)),
}

# ── Font helpers ──────────────────────────────────────────────────────────────

def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── Pick loading ──────────────────────────────────────────────────────────────

def _et_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(ET).strftime('%Y-%m-%d')
    except Exception:
        return ''


def load_top_picks(max_picks: int = 5) -> list:
    now    = datetime.now(timezone.utc)
    now_et = now.astimezone(ET)
    today  = now_et.strftime('%Y-%m-%d')

    sources = [
        ('NFL',   os.path.join(ASSETS, 'nfl-picks.json'),   True),
        ('NBA',   os.path.join(ASSETS, 'nba-picks.json'),   True),
        ('NHL',   os.path.join(ASSETS, 'nhl-picks.json'),   True),
        ('NCAAF', os.path.join(ASSETS, 'ncaaf-picks.json'), True),
        ('NCAAM', os.path.join(ASSETS, 'ncaam-picks.json'), True),
    ]

    all_picks = []
    for sport, path, spread_based in sources:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding='utf-8') as f:
                picks = json.load(f)
            for p in picks:
                gt = p.get('gameTime', '')
                if not gt or _et_date(gt) != today:
                    continue
                if datetime.fromisoformat(gt.replace('Z', '+00:00')) <= now:
                    continue  # already started
                if not p.get('confidence'):
                    continue
                p['_sport'] = sport
                se = p.get('spreadEdge')
                p['_score'] = abs(se) if se is not None else (p.get('winProb', 0.5) - 0.5) * 20
                all_picks.append(p)
        except Exception as exc:
            print(f'[Cards] Error loading {path}: {exc}')

    all_picks.sort(key=lambda p: p['_score'], reverse=True)
    return all_picks[:max_picks]


# ── Card drawing helpers ──────────────────────────────────────────────────────

def _pick_lines(p: dict) -> tuple[str, str, str, str]:
    """Return (sport, matchup, bet_line, detail_line)."""
    sport    = p.get('_sport', p.get('sport', ''))
    home     = p.get('homeTeam', '')
    away     = p.get('awayTeam', '')
    pick     = p.get('pick', '')
    wp       = round(p.get('winProb', 0.5) * 100)
    se       = p.get('spreadEdge')
    vs       = p.get('vegasSpread')
    h_sc     = p.get('predictedHomeScore', 0)
    a_sc     = p.get('predictedAwayScore', 0)
    conf     = p.get('confidence', '')

    matchup = f'{away}  @  {home}'

    if se is not None and vs is not None:
        cover    = home if se >= 0 else away
        vs_str   = f'{vs:+.1f}' if vs <= 0 else f'-{vs:.1f}'
        bet_line = f'{cover}  (edge {se:+.1f} pts vs Vegas)'
    else:
        bet_line = f'{pick}  —  {wp}% win prob'

    if sport in ('NFL', 'NCAAF'):
        detail = f'Model: {away} {a_sc:.0f}  –  {home} {h_sc:.0f}   [{conf}]'
    elif sport in ('NBA', 'NCAAM'):
        detail = f'Model: {int(a_sc)}–{int(h_sc)}   [{conf}]'
    elif sport == 'NHL':
        detail = f'Model: {a_sc:.1f}–{h_sc:.1f}   [{conf}]'
    else:
        detail = f'Model: {a_sc:.2f}–{h_sc:.2f}   [{conf}]'

    return sport, matchup, bet_line, detail


# ── Square card (1080×1080) ───────────────────────────────────────────────────

def draw_square_card(picks: list, today: str) -> Image.Image:
    W, H = 1080, 1080
    img  = Image.new('RGB', (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    f_title  = _load_font(52, bold=True)
    f_sub    = _load_font(28)
    f_sport  = _load_font(22, bold=True)
    f_match  = _load_font(30, bold=True)
    f_bet    = _load_font(32, bold=True)
    f_detail = _load_font(22)
    f_rank   = _load_font(38, bold=True)
    f_brand  = _load_font(26)

    # Header
    draw.rectangle([(0, 0), (W, 100)], fill=(20, 22, 45))
    draw.text((40, 20), "🏆 Jack's Models", font=f_title, fill=ACCENT)
    draw.text((40, 72), f"Today's Top Picks — {today}", font=f_sub, fill=GREY)

    # Pick cards
    card_h   = 160
    card_gap = 10
    start_y  = 118
    max_cards = min(len(picks), 5)

    for i, p in enumerate(picks[:max_cards]):
        sport, matchup, bet_line, detail = _pick_lines(p)
        y = start_y + i * (card_h + card_gap)
        # Card bg
        draw.rounded_rectangle([(24, y), (W - 24, y + card_h)], radius=12, fill=BG_CARD)
        # Rank circle
        draw.ellipse([(32, y + 12), (88, y + 68)], fill=(40, 44, 70))
        draw.text((45, y + 16), f'#{i+1}', font=f_rank, fill=GOLD)
        # Sport badge
        sport_bg, sport_fg = SPORT_COLORS.get(sport, ((50, 50, 80), WHITE))
        sw   = 90
        sx   = 96
        sy   = y + 14
        draw.rounded_rectangle([(sx, sy), (sx + sw, sy + 28)], radius=6, fill=sport_bg)
        draw.text((sx + 6, sy + 4), sport, font=f_sport, fill=sport_fg)
        # Matchup
        draw.text((96, y + 48), matchup, font=f_match, fill=WHITE)
        # Bet / edge line
        se = p.get('spreadEdge')
        bet_color = ORANGE if se is not None else ACCENT
        draw.text((96, y + 84), bet_line, font=f_bet, fill=bet_color)
        # Detail
        draw.text((96, y + 124), detail, font=f_detail, fill=GREY)

    # Brand footer
    draw.rectangle([(0, H - 52), (W, H)], fill=(20, 22, 45))
    draw.text((40, H - 36), 'jesimon4-scoreboard.web.app', font=f_brand, fill=GREY)
    draw.text((W - 300, H - 36), '#SportsBetting #ModelPicks', font=f_brand, fill=(80, 90, 120))

    return img


# ── Story card (1080×1920) ────────────────────────────────────────────────────

def draw_story_card(picks: list, today: str) -> Image.Image:
    W, H = 1080, 1920
    img  = Image.new('RGB', (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    f_title  = _load_font(64, bold=True)
    f_sub    = _load_font(34)
    f_sport  = _load_font(26, bold=True)
    f_match  = _load_font(36, bold=True)
    f_bet    = _load_font(40, bold=True)
    f_detail = _load_font(28)
    f_rank   = _load_font(48, bold=True)
    f_brand  = _load_font(32)

    # Header
    draw.rectangle([(0, 0), (W, 130)], fill=(20, 22, 45))
    draw.text((50, 24), "🏆 Jack's Models", font=f_title, fill=ACCENT)
    draw.text((50, 94), f"Today's Top Picks — {today}", font=f_sub, fill=GREY)

    card_h   = 240
    card_gap = 18
    start_y  = 158
    max_cards = min(len(picks), 6)

    for i, p in enumerate(picks[:max_cards]):
        sport, matchup, bet_line, detail = _pick_lines(p)
        y = start_y + i * (card_h + card_gap)
        draw.rounded_rectangle([(28, y), (W - 28, y + card_h)], radius=16, fill=BG_CARD)
        # Rank
        draw.ellipse([(40, y + 18), (108, y + 86)], fill=(40, 44, 70))
        draw.text((52, y + 24), f'#{i+1}', font=f_rank, fill=GOLD)
        # Sport badge
        sport_bg, sport_fg = SPORT_COLORS.get(sport, ((50, 50, 80), WHITE))
        sx, sy, sw = 118, y + 22, 110
        draw.rounded_rectangle([(sx, sy), (sx + sw, sy + 36)], radius=8, fill=sport_bg)
        draw.text((sx + 8, sy + 5), sport, font=f_sport, fill=sport_fg)
        # Matchup
        draw.text((118, y + 68), matchup, font=f_match, fill=WHITE)
        # Bet line
        se = p.get('spreadEdge')
        bet_color = ORANGE if se is not None else ACCENT
        draw.text((118, y + 114), bet_line, font=f_bet, fill=bet_color)
        # Detail
        draw.text((118, y + 168), detail, font=f_detail, fill=GREY)

    # Footer
    footer_y = start_y + max_cards * (card_h + card_gap) + 20
    draw.line([(50, footer_y), (W - 50, footer_y)], fill=(40, 44, 70), width=2)
    draw.text((50, footer_y + 16), 'jesimon4-scoreboard.web.app', font=f_brand, fill=GREY)
    draw.text((50, footer_y + 56), 'Free daily stat-driven sports picks', font=f_brand, fill=(80, 90, 120))

    return img


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    now_et  = datetime.now(timezone.utc).astimezone(ET)
    today   = now_et.strftime('%Y-%m-%d')
    today_f = now_et.strftime('%b %-d, %Y')

    picks = load_top_picks(max_picks=6)
    if not picks:
        print('[Cards] No picks for today — nothing to generate.')
        return

    print(f'[Cards] Generating cards for {len(picks)} picks on {today}')

    square = draw_square_card(picks, today_f)
    story  = draw_story_card(picks, today_f)

    sq_path    = os.path.join(ASSETS, 'social-picks.png')
    story_path = os.path.join(ASSETS, 'social-picks-story.png')

    square.save(sq_path,    'PNG', optimize=True)
    story.save(story_path,  'PNG', optimize=True)

    print(f'[Cards] Saved: {sq_path}')
    print(f'[Cards] Saved: {story_path}')


if __name__ == '__main__':
    main()
