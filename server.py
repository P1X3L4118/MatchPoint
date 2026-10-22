from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
API = "https://www.fotmob.com/api/data/matches"
CACHE_SECONDS = 30
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def today_iso() -> str:
    return datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()


def normalize_match(league: dict, match: dict) -> dict | None:
    home, away = match.get("home") or {}, match.get("away") or {}
    if not home.get("name") or not away.get("name"):
        return None
    status = match.get("status") or {}
    started, finished = bool(status.get("started")), bool(status.get("finished"))
    cancelled = bool(status.get("cancelled"))
    state = "cancelled" if cancelled else "finished" if finished else "live" if started else "scheduled"
    date_value = (status.get("utcTime") or "")[:10]
    kickoff = ""
    if status.get("utcTime"):
        try:
            kickoff = datetime.fromisoformat(status["utcTime"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Madrid")).strftime("%H:%M")
        except ValueError:
            pass
    if not kickoff:
        kickoff = str(match.get("time", "")).split(" ")[-1]
    return {
        "id": str(match.get("id", "")),
        "league": league.get("name", "Fútbol"),
        "leagueLogo": league.get("imageUrl", ""),
        "home": home.get("name", ""),
        "away": away.get("name", ""),
        "homeScore": home.get("score") if started or finished else None,
        "awayScore": away.get("score") if started or finished else None,
        "status": state,
        "statusText": str((match.get("status") or {}).get("reason", {}).get("short", "")),
        "minute": str(match.get("status") or {}).get("liveTime", ""),
        "date": date_value,
        "time": kickoff,
        "homeId": home.get("id"),
        "awayId": away.get("id"),
    }


def fetch_matches(day: str) -> dict:
    now = time.monotonic()
    with _lock:
        hit = _cache.get(day)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    parsed = datetime.strptime(day, "%Y-%m-%d")
    api_day = parsed.strftime("%Y%m%d")
    request = Request(f"{API}?date={api_day}", headers={
        "User-Agent": "FutbolCentral/1.0 (https://github.com/P1X3L4118/prueba)",
        "Accept": "application/json",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
    })
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"FotMob respondió HTTP {error.code}; no se ha intentado eludir el bloqueo.") from error
    except URLError as error:
        raise RuntimeError(f"No se pudo conectar con FotMob: {error.reason}") from error
    leagues = []
    all_matches = []
    for group in payload.get("leagues", []):
        normalized = [m for raw in group.get("matches", []) if (m := normalize_match(group, raw))]
        if normalized:
            leagues.append({"name": group.get("name", "Fútbol"), "matches": normalized})
            all_matches.extend(normalized)
    result = {"date": day, "updatedAt": datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="seconds"), "source": "FotMob (API no oficial)", "matches": all_matches, "leagues": leagues}
    with _lock:
        _cache[day] = (time.monotonic(), result)
    return result


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/matches":
            return super().do_GET()
        day = parse_qs(parsed.query).get("date", [today_iso()])[0]
        try:
            datetime.strptime(day, "%Y-%m-%d")
            return self.send_json(200, fetch_matches(day))
        except ValueError:
            return self.send_json(400, {"error": "La fecha debe tener formato AAAA-MM-DD."})
        except Exception as error:
            return self.send_json(502, {"error": str(error)})

    def send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Fútbol Central: http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
