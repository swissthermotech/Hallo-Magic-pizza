"""Read-only export of the whole application database to one Extended-JSON file.

Usage (from /app/backend):  python scripts/export_snapshot.py /tmp/hmp-snapshot.json
Reads MONGO_URL / DB_NAME from backend/.env (or the environment). Never writes to the database.
"""
import json
import os
import sys
from pathlib import Path

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
# Keep in sync with snapshot.COLLECTIONS (imported lazily to avoid the app's import chain)
COLLECTIONS = ["counters", "categories", "products", "extras", "settings", "staff_auth", "users", "orders",
               "print_jobs", "closings", "driver_shifts", "marketing_consents"]
out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/hmp-snapshot.json")

client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
data = {c: list(db[c].find({})) for c in COLLECTIONS}
out.write_text(json.dumps({"db_name": os.environ["DB_NAME"], "collections": data}, default=json_util.default))
print(f"exported to {out} ({out.stat().st_size // 1024} KB)")
for c in COLLECTIONS:
    print(f"  {c:20s} {len(data[c])}")
