from __future__ import annotations

import csv
import io
import json
import os
import threading
import time
from datetime import date, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


ROOT = os.path.dirname(os.path.abspath(__file__))
SEASON_START = date.today().year if date.today().month >= 7 else date.today().year - 1
SEASON = f"{SEASON_START % 100:02d}{(SEASON_START + 1) % 100:02d}"
LEAGUES = {"LaLiga": "SP1", "Premier League": "E0", "Serie A": "I1", "Bundesliga": "D1"}
CACHE_SECONDS = 900
cache: dict[str, tuple[float, list[dict]]] = {}
cache_lock = threading.Lock()


def fetch_matches(league: str) -> list[dict]:
    now = time.monotonic()
    with cache_lock:
        cached = cache.get(league)
        if cached and now - cached[0] < CACHE_SECONDS:
            return cached[1]

    division = LEAGUES[league]
    url = f"https://football-data.co.uk/mmz4281/{SEASON}/{division}.csv"
    request = Request(url, headers={"User-Agent": "FutbolCentral/1.0"})
    with urlopen(request, timeout=20) as response:
        text = response.read().decode("utf-8-sig", errors="replace")

    matches = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            kickoff = datetime.strptime(row.get("Date", "").strip(), "%d/%m/%Y").date()
        except ValueError:
            try:
                kickoff = datetime.strptime(row.get("Date", "").strip(), "%d/%m/%y").date()
            except ValueError:
                continue
        home, away = row.get("HomeTeam", "").strip(), row.get("AwayTeam", "").strip()
        if not home or not away:
            continue
        home_raw, away_raw = row.get("FTHG", "").strip(), row.get("FTAG", "").strip()
        has_score = home_raw.isdigit() and away_raw.isdigit()
        matches.append({
            "league": league,
            "date": kickoff.isoformat(),
            "time": row.get("Time", "").strip(),
            "home": home,
            "away": away,
            "homeScore": int(home_raw) if has_score else None,
            "awayScore": int(away_raw) if has_score else None,
            "status": "finished" if has_score else ("unknown" if kickoff < date.today() else ""),
        })

    if not matches:
        raise ValueError(f"El CSV de {league} no contiene partidos legibles")
    with cache_lock:
        cache[league] = (time.monotonic(), matches)
    return matches


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/football-data":
            return super().do_GET()
        league = parse_qs(parsed.query).get("league", [""])[0]
        if league not in LEAGUES:
            return self.send_json(400, {"error": "Competición no válida"})
        try:
            return self.send_json(200, {"league": league, "source": "Football-Data.co.uk", "matches": fetch_matches(league)})
        except (URLError, TimeoutError, ValueError, OSError) as error:
            return self.send_json(502, {"error": f"No se pudieron obtener los datos de {league}: {error}"})

    def send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print(f"Fútbol Central listo en http://127.0.0.1:8000 · temporada {SEASON[:2]}/{SEASON[2:]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
        server.server_close()
