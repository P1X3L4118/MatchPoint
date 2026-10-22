from __future__ import annotations

import json
import gzip
import re
import threading
import time
import unicodedata
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
API = "https://www.fotmob.com/api/data/leagues"
LEAGUES = [
    {"id": 87, "name": "LaLiga", "country": "España"},
    {"id": 47, "name": "Premier League", "country": "Inglaterra"},
    {"id": 55, "name": "Serie A", "country": "Italia"},
    {"id": 54, "name": "Bundesliga", "country": "Alemania"},
    {"id": 53, "name": "Ligue 1 McDonald's", "country": "Francia"},
]
FOOTYNTEL = {
    87: ("pd", "la-liga"),
    47: ("pl", "premier-league"),
    55: ("sa", "serie-a"),
    54: ("bl1", "bundesliga"),
    53: ("fl1", "ligue-1"),
}
CACHE_SECONDS = 300
_cache: tuple[float, dict] | None = None
_lock = threading.Lock()
MADRID = ZoneInfo("Europe/Madrid")


def fotmob_json(url: str) -> dict | list:
    request = Request(url, headers={
        "User-Agent": "FutbolCentral/1.0 (https://github.com/P1X3L4118/prueba)",
        "Accept": "application/json",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
    })
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read()
            if body.startswith(b"\x1f\x8b"):
                body = gzip.decompress(body)
            return json.loads(body.decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"FotMob respondió HTTP {error.code}; no se ha intentado eludir el bloqueo.") from error
    except URLError as error:
        raise RuntimeError(f"No se pudo conectar con FotMob: {error.reason}") from error


def local_kickoff(status: dict, fallback: str = "") -> tuple[str, str]:
    utc_time = status.get("utcTime")
    if utc_time:
        try:
            moment = datetime.fromisoformat(utc_time.replace("Z", "+00:00")).astimezone(MADRID)
            return moment.date().isoformat(), moment.strftime("%H:%M")
        except ValueError:
            pass
    return "", fallback


def normalize_match(match: dict) -> dict | None:
    home, away = match.get("home") or {}, match.get("away") or {}
    if not home.get("name") or not away.get("name"):
        return None
    status = match.get("status") or {}
    if not isinstance(status, dict):
        status = {}
    reason = status.get("reason") or {}
    if not isinstance(reason, dict):
        reason = {}
    reason_short = str(reason.get("short") or "")
    reason_long = str(reason.get("long") or reason_short)
    cancelled = bool(status.get("cancelled"))
    reason_key = f"{reason_short} {reason_long}".casefold()
    if "suspend" in reason_key:
        match_state = "suspended"
    elif ("postpon" in reason_key or "aplaz" in reason_key) and not status.get("started"):
        match_state = "postponed"
    elif cancelled:
        match_state = "cancelled"
    elif status.get("finished") or status.get("awarded"):
        match_state = "finished"
    elif status.get("started"):
        match_state = "live"
    else:
        match_state = "scheduled"
    date_value, kickoff = local_kickoff(status, str(match.get("time", "")).split(" ")[-1])
    has_score = bool(status.get("started") or status.get("finished") or status.get("awarded"))
    home_score, away_score = home.get("score"), away.get("score")
    score_text = str(status.get("scoreStr") or "")
    score_match = re.match(r"\s*(\d+)\s*[-–—:]\s*(\d+)", score_text)
    if score_match:
        home_score = home_score if home_score is not None else int(score_match.group(1))
        away_score = away_score if away_score is not None else int(score_match.group(2))
    return {
        "id": str(match.get("id", "")),
        "round": str(match.get("roundName") or match.get("round") or ""),
        "date": date_value,
        "time": kickoff,
        "home": home.get("name", ""),
        "away": away.get("name", ""),
        "homeId": home.get("id"),
        "awayId": away.get("id"),
        "homeScore": home_score if has_score else None,
        "awayScore": away_score if has_score else None,
        "status": match_state,
        "statusText": reason_long,
        "cancellationReason": reason_long if match_state in ("cancelled", "postponed", "suspended") else "",
    }


def normalize_standings(payload: dict) -> tuple[list[dict], list[dict]]:
    blocks = payload.get("table") or []
    if not blocks:
        return [], []
    data = blocks[0].get("data") or {}
    table = data.get("table") or {}
    rows = []
    for row in table.get("all") or []:
        scores = str(row.get("scoresStr") or "0-0").split("-", 1)
        goals_for = int(scores[0]) if scores and scores[0].isdigit() else 0
        goals_against = int(scores[1]) if len(scores) > 1 and scores[1].isdigit() else 0
        rows.append({
            "name": row.get("name", ""), "shortName": row.get("shortName", row.get("name", "")),
            "id": row.get("id"), "played": row.get("played", 0), "wins": row.get("wins", 0),
            "draws": row.get("draws", 0), "losses": row.get("losses", 0), "gf": goals_for,
            "ga": goals_against, "gd": row.get("goalConDiff", goals_for - goals_against),
            "points": row.get("pts", 0), "rank": row.get("idx", len(rows) + 1),
            "qualColor": row.get("qualColor", ""),
        })
    legend = data.get("legend") or []
    return rows, [{"title": item.get("title", ""), "color": item.get("color", ""), "indices": item.get("indices", [])} for item in legend]


def normalize_player_stats(payload: dict) -> tuple[list[dict], list[dict]]:
    stats = payload.get("stats") or {}
    scorers, assists = [], []
    for stat in stats.get("players") or []:
        header = str(stat.get("header") or "").casefold()
        if "scorer" in header or "goleador" in header or header in ("goals", "top scorer"):
            target = scorers
        elif header in ("assist", "assists", "asistencia", "asistencias"):
            target = assists
        else:
            continue
        players = stat.get("topThree") or []
        full_list_url = stat.get("fetchAllUrl")
        if full_list_url:
            try:
                full_list = fotmob_json(full_list_url)
                top_lists = (full_list.get("TopLists") or []) if isinstance(full_list, dict) else []
                complete = next((item.get("StatList") for item in top_lists if item.get("StatList")), [])
                if complete:
                    players = complete[:5]
            except Exception as error:
                # Conserva los líderes del endpoint principal si falla la lista ampliada.
                print(f"FotMob: no se pudo ampliar {header}: {error}")
        for player in players[:5]:
            player_id = player.get("id") or player.get("ParticipantId") or player.get("ParticiantId")
            name = player.get("name") or player.get("ParticipantName", "")
            value = player.get("value")
            if value is None:
                value = player.get("StatValue") or 0
            if isinstance(value, dict):
                value = value.get("value", 0)
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            target.append({
                "id": player_id, "name": name,
                "team": player.get("teamName") or player.get("TeamName", ""),
                "teamId": player.get("teamId") or player.get("TeamId"),
                "value": value, "rank": player.get("rank") or player.get("Rank", 0),
            })
    return scorers, assists

def club_key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").casefold()
    plain = re.sub(r"\b(?:fc|cf|afc|ssc|ac|club|clube|the|de|do|da|del|la|le|los|las|and)\b", " ", plain)
    key = re.sub(r"[^a-z0-9]", "", plain)
    aliases = {
        "barca": "barcelona", "fcbarcelona": "barcelona",
        "atleti": "atleticomadrid", "clubatleticodemadrid": "atleticomadrid",
        "realmadridcf": "realmadrid", "realbetisbalompie": "realbetis",
        "manchestercityfc": "manchestercity", "mancity": "manchestercity",
        "brightonhove": "brighton", "brightonhovealbion": "brighton",
        "fcinternazionalemilano": "inter", "internazionalemilano": "inter",
        "internazionale": "inter", "intermilan": "inter",
        "fcbayernmunchen": "bayernmunchen", "bayern": "bayernmunchen",
        "borussiadortmund": "dortmund", "bvb": "dortmund",
        "parissaintgermain": "psg", "parissg": "psg",
        "olympiquelyonnais": "lyon", "olympiquemarseille": "marseille",
        "asroma": "roma", "sslazio": "lazio",
        "bayer04leverkusen": "leverkusen", "lilleosc": "lille",
    }
    return aliases.get(key, key)


def footyntel_json(url: str) -> dict:
    request = Request(url, headers={
        "User-Agent": "FutbolCentral/1.0 (https://github.com/P1X3L4118/prueba)",
        "Accept": "application/json",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
    })
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_footyntel_title_odds(config: dict, standings: list[dict]) -> tuple[list[dict], dict | None]:
    feed = FOOTYNTEL.get(config["id"])
    if not feed:
        return [], None
    code, page = feed
    page_url = f"https://www.footyntel.com/{page}/"
    try:
        data = footyntel_json(f"https://www.footyntel.com/data/sim/{code}.json")
        source_teams = {str(team.get("id")): team for team in data.get("teams", [])}
        fotmob_teams = {club_key(row.get("name", "")): row for row in standings}
        rows = []
        for forecast in data.get("projection", []):
            source_team = source_teams.get(str(forecast.get("id")))
            if not source_team:
                continue
            external_name = source_team.get("name", "")
            local_team = fotmob_teams.get(club_key(external_name))
            if not local_team:
                print(f"Footyntel: no se encontrÃ³ equipo de FotMob para {config['name']}: {external_name}")
            probability = max(0.0, min(100.0, float(forecast.get("title", 0) or 0)))
            rows.append({
                "id": local_team.get("id") if local_team else None,
                "name": (local_team.get("shortName") or local_team.get("name")) if local_team else external_name,
                "probability": round(probability, 1),
                "_rank": int(local_team.get("rank", 999)) if local_team else 999,
            })
        rows.sort(key=lambda row: (-row["probability"], row["_rank"]))
        for row in rows:
            row.pop("_rank", None)
        source = {
            "name": "Footyntel",
            "url": page_url,
            "updatedAt": data.get("updated"),
            "simulations": data.get("simulations"),
            "license": "CC BY 4.0",
        }
        return rows[:3], source
    except Exception as error:
        print(f"Footyntel: no se pudieron actualizar las predicciones de {config['name']}: {error}")
        return [], None


def fetch_all_data(force: bool = False) -> dict:
    global _cache
    now = time.monotonic()
    with _lock:
        if not force and _cache and now - _cache[0] < CACHE_SECONDS:
            return _cache[1]
    result_leagues = []
    for config in LEAGUES:
        payload = fotmob_json(f"{API}?id={config['id']}")
        fixtures_data = payload.get("fixtures") or {}
        fixtures = [item for raw in fixtures_data.get("allMatches", []) if (item := normalize_match(raw))]
        standings, legend = normalize_standings(payload)
        scorers, assists = normalize_player_stats(payload)
        title_odds, title_odds_source = fetch_footyntel_title_odds(config, standings)
        result_leagues.append({
            **config,
            "logo": f"https://images.fotmob.com/image_resources/logo/leaguelogo/{config['id']}.png",
            "matches": fixtures,
            "standings": standings,
            "legend": legend,
            "scorers": scorers,
            "assists": assists,
            "titleOdds": title_odds,
            "titleOddsSource": title_odds_source,
        })
    result = {
        "updatedAt": datetime.now(MADRID).isoformat(timespec="seconds"),
        "source": "FotMob (API no oficial)",
        "leagues": result_leagues,
    }
    with _lock:
        _cache = (time.monotonic(), result)
    return result


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path != "/api/football":
            return super().do_GET()
        try:
            return self.send_json(200, fetch_all_data())
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

