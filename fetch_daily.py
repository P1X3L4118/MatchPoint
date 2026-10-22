from __future__ import annotations

import json
import sys
from pathlib import Path

from server import fetch_all_data

output = Path(sys.argv[1] if len(sys.argv) > 1 else "data/football.json")
payload = fetch_all_data(force=True)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Guardadas {len(payload['leagues'])} ligas y {sum(len(league['matches']) for league in payload['leagues'])} partidos en {output}")
