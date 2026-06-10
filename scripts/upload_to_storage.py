"""
Upload frequently-updated MLB CSVs to Firebase Storage so the live app
fetches them directly without requiring a full Angular rebuild.

Called from both update-mlb-lineups.yml and update-mlb-data.yml after
the CSV files have been refreshed.
"""

import json
import os
import sys

try:
    import firebase_admin
    from firebase_admin import credentials, storage as fb_storage
except ImportError:
    print('[Storage] firebase-admin not installed; skipping upload.')
    sys.exit(0)

BUCKET = 'jesimon4-scoreboard.appspot.com'
ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'src', 'assets')
)
FILES = [
    'MLB-Lineups.csv',
    'MLB-Player-Props.csv',
    'top-picks.json',
]


def upload():
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not sa_json:
        print('[Storage] FIREBASE_SERVICE_ACCOUNT env var not set; skipping.')
        return

    cred = credentials.Certificate(json.loads(sa_json))
    firebase_admin.initialize_app(cred, {'storageBucket': BUCKET})
    bucket = fb_storage.bucket()

    for filename in FILES:
        local_path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(local_path):
            print(f'[Storage] File not found, skipping: {filename}')
            continue
        content_type = 'application/json' if filename.endswith('.json') else 'text/csv'
        blob = bucket.blob(filename)
        blob.upload_from_filename(local_path, content_type=content_type)
        print(f'[Storage] Uploaded {filename} → gs://{BUCKET}/{filename}')

    print('[Storage] Done.')


if __name__ == '__main__':
    upload()
