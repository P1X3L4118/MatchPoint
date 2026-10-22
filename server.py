from __future__ import annotations

import json
import gzip
import math
import random
import re
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
API = "https://www.fotmob.com/api/data/leagues"
LEAGUES = [
    {"id": 87, "name": "LaLiga", "country": "España"},
    {"id": 47, "name": "Premier League", "country": "Inglaterra"},
    {"id": 55, "name": "Serie A", "country": "Italia"},
    {"id": 54, "name": "Bundesliga", "country": "Alemania"},
    {"id": 53, "name": "Ligue 1 McDonald's", "country": "Francia"},
]
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

def _poisson(mean: float, rng: random.Random) -> int:
    threshold = math.exp(-mean)
    product = 1.0
    goals = 0
    while product > threshold:
        goals += 1
        product *= rng.random()
    return goals - 1


def estimate_title_odds(league_id: int, standings: list[dict], matches: list[dict]) -> list[dict]:
    """Estima el título simulando los resultados de los partidos pendientes."""
    if len(standings) < 2:
        return []
    by_id = {str(row.get("id")): index for index, row in enumerate(standings) if row.get("id") is not None}
    played_total = sum(max(0, int(row.get("played") or 0)) for row in standings)
    goals_total = sum(max(0, int(row.get("gf") or 0)) for row in standings)
    avg_goals = goals_total / played_total if played_total else 1.35
    avg_goals = max(0.6, min(2.2, avg_goals))
    prior_games = 8
    teams = []
    for row in standings:
        played = max(0, int(row.get("played") or 0))
        gf = max(0, int(row.get("gf") or 0))
        ga = max(0, int(row.get("ga") or 0))
        attack = (gf + prior_games * avg_goals) / (played + prior_games) / avg_goals
        defense = (ga + prior_games * avg_goals) / (played + prior_games) / avg_goals
        teams.append({
            "id": row.get("id"), "name": row.get("name", ""),
            "points": int(row.get("points") or 0), "gd": int(row.get("gd") or 0), "gf": gf,
            "attack": max(0.55, min(1.65, attack)), "defense": max(0.55, min(1.65, defense)),
        })
    today = datetime.now(MADRID).date().isoformat()
    remaining = []
    for match in matches:
        if match.get("status") not in ("scheduled", "postponed"):
            continue
        if not match.get("date") or match["date"] < today:
            continue
        home, away = by_id.get(str(match.get("homeId"))), by_id.get(str(match.get("awayId")))
        if home is None or away is None or home == away:
            continue
        home_rate = avg_goals * teams[home]["attack"] * teams[away]["defense"] * 1.08
        away_rate = avg_goals * teams[away]["attack"] * teams[home]["defense"] * 0.92
        remaining.append((home, away, max(0.15, min(4.5, home_rate)), max(0.15, min(4.5, away_rate))))
    if not remaining:
        champion = max(range(len(teams)), key=lambda i: (teams[i]["points"], teams[i]["gd"], teams[i]["gf"]))
        ranking = sorted(range(len(teams)), key=lambda i: (i == champion, teams[i]["points"], teams[i]["gd"]), reverse=True)[:3]
        return [{"id": teams[i]["id"], "name": teams[i]["name"], "probability": 100.0 if i == champion else 0.0} for i in ranking]
    rng = random.Random(league_id)
    wins = [0] * len(teams)
    trials = 10000
    for _ in range(trials):
        points = [team["points"] for team in teams]
        goal_diff = [team["gd"] for team in teams]
        goals_for = [team["gf"] for team in teams]
        for home, away, home_rate, away_rate in remaining:
            hg, ag = _poisson(home_rate, rng), _poisson(away_rate, rng)
            goal_diff[home] += hg - ag
            goal_diff[away] += ag - hg
            goals_for[home] += hg
            goals_for[away] += ag
            if hg > ag:
                points[home] += 3
            elif hg < ag:
                points[away] += 3
            else:
                points[home] += 1
                points[away] += 1
        winner = max(range(len(teams)), key=lambda i: (points[i], goal_diff[i], goals_for[i]))
        wins[winner] += 1
    ranking = sorted(range(len(teams)), key=lambda i: (-wins[i], -teams[i]["points"], -teams[i]["gd"]))[:3]
    return [{"id": teams[i]["id"], "name": teams[i]["name"], "probability": round(wins[i] * 100 / trials, 1)} for i in ranking]


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
        title_odds = estimate_title_odds(config["id"], standings, fixtures)
        result_leagues.append({
            **config,
            "logo": f"https://images.fotmob.com/image_resources/logo/leaguelogo/{config['id']}.png",
            "matches": fixtures,
            "standings": standings,
            "legend": legend,
            "scorers": scorers,
            "assists": assists,
            "titleOdds": title_odds,
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

