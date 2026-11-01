"""
Fetch NBA team efficiency stats via the nba_api package and write NBA-Stats.csv.

Column mapping (values are OffRtg/100, DefRtg/100, Pace as possessions/game):
  Off        = season OffRtg / 100
  oLastThree = last-3-game OffRtg / 100
  oHome      = home OffRtg / 100
  oAway      = road OffRtg / 100
  adjO       = season OffRtg / 100 (same as Off)
  Def        = season DefRtg / 100
  dLastThree = last-3-game DefRtg / 100
  dHome      = home DefRtg / 100
  dAway      = road DefRtg / 100
  adjD       = season DefRtg / 100 (same as Def)
  Tempo      = Pace (possessions per 48 min ≈ per game)
  adjT       = team Pace / league-average Pace

Falls back to prior season when average games played < 3.
"""

import csv
import os
import time
from datetime import datetime

ASSETS = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
OUTPUT = os.path.join(ASSETS, 'NBA-Stats.csv')

NAME_FIXES = {
    'LA Clippers': 'Los Angeles Clippers',
}


def current_season() -> tuple[str, str]:
    now = datetime.now()
    y   = now.year if now.month >= 10 else now.year - 1
    cur   = f'{y}-{str(y + 1)[-2:]}'    # e.g. "2026-27"
    prior = f'{y - 1}-{str(y)[-2:]}'    # e.g. "2025-26"
    return cur, prior


def fetch_advanced(season: str, last_n: int = 0, location: str = '') -> list[dict]:
    from nba_api.stats.endpoints import leaguedashteamstats
    label = f'{season} last_n={last_n} loc={location or "all"}'
    try:
        kwargs = dict(
            measure_type_detailed_defense='Advanced',
            per_mode_simple='PerGame',
            season=season,
            season_type_all_star='Regular Season',
            last_n_games=last_n,
            location_nullable=location,
        )
        df = leaguedashteamstats.LeagueDashTeamStats(**kwargs).get_data_frames()[0]
        rows = df.to_dict('records')
        print(f'[NBA Stats] {label}: {len(rows)} teams')
        return rows
    except Exception as exc:
        print(f'[NBA Stats] {label} error: {exc}')
        return []


def avg_gp(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(float(r.get('GP', 0)) for r in rows) / len(rows)


def rows_to_map(rows: list[dict]) -> dict[str, dict]:
    m = {}
    for r in rows:
        name = NAME_FIXES.get(r['TEAM_NAME'], r['TEAM_NAME'])
        m[name] = r
    return m


def main():
    cur_season, prior_season = current_season()
    print(f'[NBA Stats] Current season: {cur_season}  Prior: {prior_season}')

    overall = fetch_advanced(cur_season)
    time.sleep(1)

    if avg_gp(overall) < 3:
        print(f'[NBA Stats] Current season sparse ({avg_gp(overall):.1f} GP avg) — using {prior_season}.')
        overall = fetch_advanced(prior_season)
        time.sleep(1)
        season = prior_season
    else:
        season = cur_season

    if not overall:
        print('[NBA Stats] No data — aborting.')
        return

    last3 = fetch_advanced(season, last_n=3);   time.sleep(1)
    home  = fetch_advanced(season, location='Home'); time.sleep(1)
    road  = fetch_advanced(season, location='Road'); time.sleep(1)

    overall_map = rows_to_map(overall)
    last3_map   = rows_to_map(last3)
    home_map    = rows_to_map(home)
    road_map    = rows_to_map(road)

    paces   = [float(r.get('PACE', 100)) for r in overall if r.get('PACE')]
    lg_pace = sum(paces) / len(paces) if paces else 100.0
    print(f'[NBA Stats] League-average Pace: {lg_pace:.2f}')

    def _r(row: dict | None, key: str, fallback: float = 1.0) -> float:
        if not row:
            return round(fallback, 6)
        try:
            return round(float(row[key]) / 100, 6)
        except (KeyError, TypeError, ValueError):
            return round(fallback, 6)

    def _pace(row: dict | None) -> float:
        try:
            return round(float(row['PACE']), 2)  # type: ignore[index]
        except (KeyError, TypeError, ValueError, AttributeError):
            return round(lg_pace, 2)

    csv_rows = []
    for team_name in sorted(overall_map):
        ov = overall_map[team_name]
        l3 = last3_map.get(team_name)
        hm = home_map.get(team_name)
        rd = road_map.get(team_name)

        off_r  = _r(ov, 'OFF_RATING')
        def_r  = _r(ov, 'DEF_RATING')
        tempo  = _pace(ov)

        csv_rows.append({
            'Team':        team_name,
            'Off':         off_r,
            'oLastThree':  _r(l3, 'OFF_RATING', off_r),
            'oHome':       _r(hm, 'OFF_RATING', off_r),
            'oAway':       _r(rd, 'OFF_RATING', off_r),
            'adjO':        off_r,
            'Def':         def_r,
            'dLastThree':  _r(l3, 'DEF_RATING', def_r),
            'dHome':       _r(hm, 'DEF_RATING', def_r),
            'dAway':       _r(rd, 'DEF_RATING', def_r),
            'adjD':        def_r,
            'Tempo':       tempo,
            'adjT':        round(tempo / lg_pace, 6),
        })

    fieldnames = ['Team','Off','oLastThree','oHome','oAway','adjO',
                  'Def','dLastThree','dHome','dAway','adjD','Tempo','adjT']
    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f'[NBA Stats] Wrote {len(csv_rows)} teams -> {OUTPUT}')


if __name__ == '__main__':
    main()
