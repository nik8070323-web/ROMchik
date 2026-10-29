#!/usr/bin/env python3
"""Interactive Desktop OAuth. Secrets are written locally, never printed."""
import argparse
import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

parser = argparse.ArgumentParser()
parser.add_argument('client_json', type=Path)
parser.add_argument('--scope', choices=['drive', 'drive.file'], default='drive.file')
args = parser.parse_args()
path = Path(__file__).resolve().parents[1] / '.secrets' / 'drive.env'
path.parent.mkdir(mode=0o700, exist_ok=True)
if path.exists():
    raise SystemExit('Credential file already exists; back it up before reauthorizing.')
flow = InstalledAppFlow.from_client_secrets_file(str(args.client_json), ['https://www.googleapis.com/auth/' + args.scope])
credentials = flow.run_local_server(port=0, access_type='offline', prompt='consent')
if not credentials.refresh_token:
    raise SystemExit('Google did not issue an offline refresh token.')
values = {'GOOGLE_CLIENT_ID': credentials.client_id, 'GOOGLE_CLIENT_SECRET': credentials.client_secret,
          'GOOGLE_REFRESH_TOKEN': credentials.refresh_token}
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    for key, value in values.items():
        stream.write(key + '=' + json.dumps(value) + '\n')
print('Credentials saved in .secrets/drive.env (mode 0600). Do not send this file in chat or commit it.')
