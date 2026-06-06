"""
Generate MLB-Player-Props.csv from today's lineups and probable starting pitchers.

For each batter in today's lineups:
  - Applies the same matchup formulas as scoreboard.component.ts
  - Uses today's probable starting pitcher and home ballpark park factors
  - Falls back to league-average pitcher stats if pitcher is unknown

Output columns: Hitters, Homer %, Hit%, xBases  (sorted by xBases desc)
"""

import os
from datetime import date

import pandas as pd
import statsapi
import unicodedata

# PA constants by batting order position (1-9), from scoreboard.component.ts
PA_BY_POSITION = [4.65, 4.55, 4.43, 4.33, 4.24, 4.13, 4.01, 3.90, 3.77]

# League-average batter stats used when a lineup player has <100 PA this season
LG_AVG_BATTER = {
    'k_percent': 21.377,
    'bb_percent': 9.3317,
    'xba':        0.2407,
    'xslg':       0.3878,
    'xobp':       0.320657,
    'single%':    0.13425,
    'double%':    0.0409,
    'triple%':    0.00367,
    'home_run%':  0.02555,
    'xOPS':       0.7085,
    'wRops':      1.0,
    'wLops':      1.0,
}

# League-average pitcher stats used when today's starter is unknown
LG_AVG_PITCHER = {
    'xba': 0.2407,
    'xslg': 0.3878,
    'xobp': 0.320657,
    'single%': 0.13425,
    'double%': 0.0409,
    'triple%': 0.00367,
    'home_run%': 0.02555,
    'k_percent': 21.377,
    'bb_percent': 9.3317,
    'Hand': 'R',
}

# Neutral park factors (all 1.0) when home team is unknown
NEUTRAL_PARK = {
    'w1B': 1.0, 'w2B': 1.0, 'w3B': 1.0, 'wHR': 1.0,
    'wBB': 1.0, 'wSO': 1.0, 'wRest': 1.0, 'wOBP': 1.0,
}

ASSETS = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
OUTPUT = os.path.join(ASSETS, 'MLB-Player-Props.csv')


def _ascii(name):
    return unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode('ascii')


def _pitcher_stat(pitcher, key, default):
    val = pitcher.get(key, default)
    try:
        val = float(val)
    except (TypeError, ValueError):
        return default
    return val if val > 0 else default


def load_hitters(path):
    df = pd.read_csv(path, encoding='utf-8')
    result = {}
    float_cols = [
        'k_percent', 'bb_percent', 'xba', 'xslg', 'xobp',
        'single%', 'double%', 'triple%', 'home_run%', 'xOPS', 'wRops', 'wLops',
    ]
    for _, row in df.iterrows():
        key = _ascii(str(row['Name']).strip())
        entry = {}
        for col in float_cols:
            try:
                entry[col] = float(row[col]) if col in df.columns else 0.0
            except (TypeError, ValueError):
                entry[col] = 0.0
        result[key] = entry
    return result


def load_pitchers(path):
    df = pd.read_csv(path, encoding='utf-8')
    result = {}
    float_cols = [
        'k_percent', 'bb_percent', 'xba', 'xslg', 'xobp',
        'single%', 'double%', 'triple%', 'home_run%',
    ]
    for _, row in df.iterrows():
        key = _ascii(str(row['Name']).strip())
        entry = {'Hand': str(row.get('Hand', 'R')).strip()}
        for col in float_cols:
            try:
                entry[col] = float(row[col]) if col in df.columns else 0.0
            except (TypeError, ValueError):
                entry[col] = 0.0
        result[key] = entry
    return result


def load_ballparks(path):
    df = pd.read_csv(path, encoding='utf-8')
    result = {}
    park_cols = ['w1B', 'w2B', 'w3B', 'wHR', 'wBB', 'wSO', 'wRest', 'wOBP']
    for _, row in df.iterrows():
        key = str(row['Team']).strip()
        entry = {}
        for col in park_cols:
            try:
                entry[col] = float(row[col]) if col in df.columns else 1.0
            except (TypeError, ValueError):
                entry[col] = 1.0
        result[key] = entry
    return result


def load_lineups(path):
    """Return {team_name: [player_pos1, ..., player_pos9]} (None if slot missing)."""
    df = pd.read_csv(path, encoding='utf-8')
    result = {}
    for _, row in df.iterrows():
        team_slot = str(row['Team']).strip()
        player = str(row['Player']).strip()
        for slot in range(9, 0, -1):
            if team_slot.endswith(str(slot)):
                team = team_slot[: -len(str(slot))]
                if team not in result:
                    result[team] = [None] * 9
                result[team][slot - 1] = player
                break
    return result


def compute_props(batter, pitcher, park, batting_slot):
    pa = PA_BY_POSITION[batting_slot]
    pitcher_hand = str(pitcher.get('Hand', 'R')).strip()

    if pitcher_hand == 'R':
        platoon = float(batter.get('wRops', 1.0))
        platoon_k = float(batter.get('wLops', 1.0))
    else:
        platoon = float(batter.get('wLops', 1.0))
        platoon_k = float(batter.get('wRops', 1.0))

    def adj(batter_val, pitcher_val, lg_avg, park_f):
        return float(batter_val) * (_pitcher_stat(pitcher, pitcher_val, lg_avg) / lg_avg) * platoon * park_f

    single = adj(batter['single%'], 'single%', 0.13425, park['w1B'])
    double = adj(batter['double%'], 'double%', 0.0409,  park['w2B'])
    triple = adj(batter['triple%'], 'triple%', 0.00367, park['w3B'])
    hr     = adj(batter['home_run%'], 'home_run%', 0.02555, park['wHR'])
    xba_adj  = float(batter['xba'])  * (_pitcher_stat(pitcher, 'xba',  0.2407) / 0.2407)  * platoon * park['wRest']
    xslg_adj = float(batter['xslg']) * (_pitcher_stat(pitcher, 'xslg', 0.3878) / 0.3878)  * platoon * park['wRest']
    bb = (float(batter['bb_percent']) * (_pitcher_stat(pitcher, 'bb_percent', 9.3317) / 9.3317) * platoon / 100) * park['wBB']

    ab = pa * (1.0 - bb)
    hit_sum = single + double + triple + hr

    homer_pct = 1.0 - (1.0 - hr) ** pa
    hit_pct = ((1.0 - (1.0 - xba_adj) ** ab) + (1.0 - (1.0 - hit_sum) ** pa)) / 2.0
    x_bases = (xslg_adj * ab + (single + 2 * double + 3 * triple + 4 * hr) * pa) / 2.0 - 0.19

    return homer_pct, hit_pct, x_bases


def fetch_mlb_player_props():
    today = date.today().strftime('%m/%d/%Y')
    print('[Props] Generating player props for', today)

    hitters   = load_hitters(os.path.join(ASSETS, 'MLB-Hitters.csv'))
    pitchers  = load_pitchers(os.path.join(ASSETS, 'MLB-Pitchers.csv'))
    ballparks = load_ballparks(os.path.join(ASSETS, 'MLB-Ballparks.csv'))
    lineups   = load_lineups(os.path.join(ASSETS, 'MLB-Lineups.csv'))
    print('[Props]', len(hitters), 'hitters,', len(pitchers), 'pitchers,',
          len(lineups), 'team lineups loaded.')

    schedule = statsapi.schedule(date=today, sportId=1)
    if not schedule:
        print('[Props] No games scheduled today.')
        return

    # Map each team to (opposing probable pitcher name, home team name)
    game_info = {}
    for game in schedule:
        home = game.get('home_name', '')
        away = game.get('away_name', '')
        home_pitcher = game.get('home_probable_pitcher', '')
        away_pitcher = game.get('away_probable_pitcher', '')
        # Home batters face away pitcher; away batters face home pitcher
        # Both play in the home team's park
        game_info[home] = (away_pitcher, home)
        game_info[away] = (home_pitcher, home)

    rows = []
    missing_hitters = set()
    missing_pitchers = set()

    for team, lineup in lineups.items():
        if team not in game_info:
            print('[Props]   Skipping', team, '(not in today schedule)')
            continue

        opp_pitcher_name, home_team = game_info[team]
        park = ballparks.get(home_team, NEUTRAL_PARK)

        pitcher_key = _ascii(opp_pitcher_name)
        pitcher = pitchers.get(pitcher_key)
        if pitcher is None:
            if opp_pitcher_name:
                missing_pitchers.add(opp_pitcher_name)
            pitcher = LG_AVG_PITCHER

        for slot, player_name in enumerate(lineup):
            if not player_name:
                continue
            batter_key = _ascii(player_name)
            batter = hitters.get(batter_key)
            if batter is None:
                missing_hitters.add(player_name)
                batter = LG_AVG_BATTER

            homer_pct, hit_pct, x_bases = compute_props(batter, pitcher, park, slot)
            rows.append({
                'Hitters': player_name,
                'Homer %': homer_pct,
                'Hit%': hit_pct,
                'xBases': x_bases,
            })

    if missing_hitters:
        print('[Props] Hitters not in MLB-Hitters.csv:', ', '.join(sorted(missing_hitters)))
    if missing_pitchers:
        print('[Props] Pitchers not in MLB-Pitchers.csv:', ', '.join(sorted(missing_pitchers)))

    if rows:
        df = pd.DataFrame(rows)
        df = df.sort_values('xBases', ascending=False).reset_index(drop=True)
        df.to_csv(OUTPUT, index=False)
        print('[Props] Saved', len(df), 'rows ->', OUTPUT)
    else:
        print('[Props] No rows generated.')


if __name__ == '__main__':
    fetch_mlb_player_props()
