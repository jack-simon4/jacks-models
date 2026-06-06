"""
Master script: runs all MLB data-fetch scripts in sequence.
Called by the GitHub Actions workflow (and usable locally).

Usage:
  python scripts/update_mlb.py
"""

import subprocess
import sys
import os

SCRIPTS = [
    'fetch_mlb_pitchers.py',
    'fetch_mlb_hitters.py',
    'fetch_mlb_lineups.py',
]

script_dir = os.path.dirname(os.path.abspath(__file__))

for script in SCRIPTS:
    path = os.path.join(script_dir, script)
    print(f'\n{"="*50}')
    print(f'Running {script}')
    print('='*50)
    result = subprocess.run([sys.executable, path], check=False)
    if result.returncode != 0:
        print(f'[update_mlb] {script} exited with code {result.returncode}')
        sys.exit(result.returncode)

print('\n✓ All MLB data updated successfully.')
