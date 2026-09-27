"""Import a snapshot file into a FRESH production backend through its API (never a direct DB connection).

Usage:  PROD_MANAGER_PIN=... SNAPSHOT_IMPORT_TOKEN=... python scripts/import_snapshot.py https://<prod-host> /tmp/hmp-snapshot.json
The token is read from the environment / backend/.env – never printed. Every request is small (chunks of 100 docs)
so it passes any gateway body limit. Prints the per-collection counts before and after.
"""
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
base = sys.argv[1].rstrip("/") + "/api"
snap = json.loads(Path(sys.argv[2]).read_text())
pin = os.environ.get("PROD_MANAGER_PIN") or input("Production manager PIN: ")
token = os.environ["SNAPSHOT_IMPORT_TOKEN"]
CHUNK = 100

with httpx.Client(timeout=60) as c:
    r = c.post(f"{base}/auth/staff/login", json={"pin": pin}); r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['access_token']}", "X-Import-Token": token}
    st = c.get(f"{base}/admin/snapshot/status", headers=h); st.raise_for_status()
    print("target before:", st.json())
    if not st.json()["import_token_configured"]:
        sys.exit("SNAPSHOT_IMPORT_TOKEN is not configured on the target backend")
    r = c.post(f"{base}/admin/snapshot/begin", headers=h)
    if r.status_code != 200:
        sys.exit(f"begin refused: {r.status_code} {r.text}")
    for coll, docs in snap["collections"].items():
        first = True
        for i in range(0, max(len(docs), 1), CHUNK):
            r = c.post(f"{base}/admin/snapshot/import", headers=h, json={"collection": coll, "docs": docs[i:i + CHUNK], "first": first})
            r.raise_for_status()
            first = False
        print(f"  {coll:20s} {len(docs):5d} -> {r.json()['total']}")
    r = c.post(f"{base}/admin/snapshot/finish", headers=h); r.raise_for_status()
    print("target after:", r.json()["counts"])
