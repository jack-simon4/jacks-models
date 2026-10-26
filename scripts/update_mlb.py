"""
Master script: runs all MLB data-fetch scripts in sequence.
Called by the GitHub Actions workflow (and usable locally).

Usage:
  python scripts/update_mlb.py
"""

import subprocess
import sys
import os

# Scripts that must succeed — fail the job if these exit non-zero
REQUIRED_SCRIPTS = [
    'fetch_mlb_pitchers.py',
    'fetch_mlb_hitters.py',
]

# Scripts that are best-effort — log failures but don't block the deploy
# (no games during World Series off-days, playoffs, etc.)
OPTIONAL_SCRIPTS = [
    'fetch_mlb_lineups.py',
    'fetch_mlb_player_props.py',
]

script_dir = os.path.dirname(os.path.abspath(__file__))

def run_script(path, required):
    print(f'\n{"="*50}')
    print(f'Running {os.path.basename(path)}')
    print('='*50)
    result = subprocess.run([sys.executable, path], check=False)
    if result.returncode != 0:
        if required:
            print(f'[update_mlb] {os.path.basename(path)} failed (required) — aborting.')
            sys.exit(result.returncode)
        else:
            print(f'[update_mlb] {os.path.basename(path)} failed (optional) — skipping.')

for script in REQUIRED_SCRIPTS:
    run_script(os.path.join(script_dir, script), required=True)

for script in OPTIONAL_SCRIPTS:
    run_script(os.path.join(script_dir, script), required=False)

print('\nMLB data update complete.')
