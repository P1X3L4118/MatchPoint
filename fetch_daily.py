from __future__ import annotations

import json
import sys
from pathlib import Path

from server import fetch_matches, today_iso

output = Path(sys.argv[1] if len(sys.argv) > 1 else "data/today.json")
payload = fetch_matches(today_iso())
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Escritos {len(payload['matches'])} partidos en {output}")
