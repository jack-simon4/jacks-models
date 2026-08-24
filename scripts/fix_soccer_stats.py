"""
One-time cleanup of Soccer-Stats.csv.
  - Removes duplicate rows created when the API returned "Arsenal FC" instead
    of "Arsenal" (FC-suffix variants not in FD_TO_CSV auto-added as new rows
    with single-game raw data).
  - Removes stale garbage rows (empty teams, non-league teams, etc.)
  - Renames legitimate newly-promoted teams (FC suffix → clean name) and
    seeds them with a reasonable PL-newcomer baseline instead of 1-game data.
"""
import csv, os

ASSETS   = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'src', 'assets'))
CSV_PATH = os.path.join(ASSETS, 'Soccer-Stats.csv')

# Teams that already have a proper entry under a different name — delete these
DUPLICATES = {
    'Arsenal FC',
    'Aston Villa FC',
    'AFC Bournemouth',
    'Brentford FC',
    'Brighton & Hove Albion FC',
    'Crystal Palace FC',
    'Everton FC',
    'Leeds United FC',
    'Liverpool FC',
    'Manchester City FC',
    'Manchester United FC',
    'Newcastle United FC',
    'Nottingham Forest FC',
    'Sunderland AFC',
    'Tottenham Hotspur FC',
    'Racing Club de Lens',
    'Lille OSC',
    # Stale / empty rows
    'ES Troyes AC',
    'Frosinone Calcio',
    'Le Mans FC',
    'Málaga CF',
    'Real Racing Club de Santander',
    'RC Deportivo La Coruña',
}

# FC-suffix rows that DON'T have a proper entry yet — rename them and reset
# to a sensible baseline rather than keeping 1-game extremes
RENAMES = {
    'Ipswich Town FC':  'Ipswich Town',
    'Coventry City FC': 'Coventry City',
    'Hull City AFC':    'Hull City',
}

# Reasonable baseline for a newly promoted PL side
NEWLY_PROMOTED = {
    'GF': '1.1', 'GA': '1.65',
    'wGF': '0.808', 'wGA': '1.211',
    'wLeague': '90.6', 'HomeAdv': '0.1',
}

with open(CSV_PATH, newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

cleaned = []
removed = []
renamed = []

for row in rows:
    team = row['Team']
    if team in DUPLICATES:
        removed.append(team)
        continue
    if team in RENAMES:
        new_name = RENAMES[team]
        row = {**row, 'Team': new_name, **NEWLY_PROMOTED}
        renamed.append(f'{team} -> {new_name}')
    cleaned.append(row)

with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cleaned)

print(f'Removed {len(removed)} duplicate/corrupt rows:')
for t in removed:
    print(f'  - {t}')
print(f'\nRenamed {len(renamed)} rows with fresh baseline:')
for r in renamed:
    print(f'  {r}')
print(f'\nFinal row count: {len(cleaned)}')
