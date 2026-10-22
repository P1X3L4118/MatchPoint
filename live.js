const $ = (selector) => document.querySelector(selector);
const LEAGUE_ORDER = [87, 47, 55, 54, 53];
const state = { data: null, leagueId: Number(localStorage.getItem("fc-league")) || 87, date: madridDate(), loading: false };

function madridDate(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  return `${parts.find((part) => part.type === "year").value}-${parts.find((part) => part.type === "month").value}-${parts.find((part) => part.type === "day").value}`;
}
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const initials = (name) => String(name || "?").trim().split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
const teamLogo = (id) => `https://images.fotmob.com/image_resources/logo/teamlogo/${encodeURIComponent(id)}.png`;
const leagueLogo = (id) => `https://images.fotmob.com/image_resources/logo/leaguelogo/${encodeURIComponent(id)}.png`;
const playerPhoto = (id) => `https://images.fotmob.com/image_resources/playerimages/${encodeURIComponent(id)}.png`;
const fmtDate = (date) => new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Madrid" }).format(new Date(`${date}T12:00:00`));
const fmtShortDate = (date) => new Intl.DateTimeFormat("es-ES", { weekday: "short", day: "numeric", month: "short", timeZone: "Europe/Madrid" }).format(new Date(`${date}T12:00:00`));

function activeLeague() {
  return state.data?.leagues?.find((league) => Number(league.id) === state.leagueId) || state.data?.leagues?.[0];
}
function teamImage(id, name, small = false) {
  const safeId = String(id ?? "").replace(/[^\d]/g, "");
  return `<span class="crest-wrap ${small ? "small" : ""}">${safeId ? `<img class="crest" src="${teamLogo(safeId)}" alt="" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false">` : ""}<span class="crest-fallback" ${safeId ? "hidden" : ""}>${esc(initials(name))}</span></span>`;
}
function renderLeagueNav() {
  const leagues = [...(state.data?.leagues || [])].sort((a, b) => LEAGUE_ORDER.indexOf(Number(a.id)) - LEAGUE_ORDER.indexOf(Number(b.id)));
  $("#league-nav").innerHTML = leagues.map((league) => `<button class="league-link ${Number(league.id) === state.leagueId ? "active" : ""}" type="button" data-league="${Number(league.id)}"><span class="side-league-logo"><img src="${leagueLogo(league.id)}" alt="" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span hidden>${esc(initials(league.name))}</span></span><span class="side-league-copy"><b>${esc(league.name)}</b><small>${esc(league.country)}</small></span><span class="nav-chevron">›</span></button>`).join("");
  $("#league-nav").querySelectorAll("[data-league]").forEach((button) => button.addEventListener("click", () => {
    state.leagueId = Number(button.dataset.league);
    localStorage.setItem("fc-league", String(state.leagueId));
    renderAll();
  }));
}
function renderHeader(league) {
  if (!league) return;
  $("#league-logo").src = leagueLogo(league.id);
  $("#league-logo").onerror = () => { $("#league-logo").hidden = true; };
  $("#league-logo").hidden = false;
  $("#league-country").textContent = `${league.country} · PRIMERA DIVISIÓN`;
  $("#league-title").textContent = league.name;
  $("#crumb-league").textContent = league.name.toLocaleUpperCase("es-ES");
  $("#match-league-kicker").textContent = league.name.toLocaleUpperCase("es-ES");
  const year = Number(state.date.slice(0, 4));
  const month = Number(state.date.slice(5, 7));
  const start = month >= 7 ? year : year - 1;
  $("#season-label").textContent = `${start}/${start + 1}`;
  $("#table-season").textContent = `${start}/${String(start + 1).slice(-2)}`;
}
function matchStatus(match) {
  if (match.status === "live") return { label: "EN JUEGO", className: "live" };
  if (match.status === "finished") return { label: "FINALIZADO", className: "finished" };
  if (match.status === "cancelled") return { label: "ANULADO", className: "cancelled" };
  if (match.status === "postponed") return { label: "APLAZADO", className: "postponed" };
  if (match.status === "suspended") return { label: "SUSPENDIDO", className: "cancelled" };
  return { label: match.time || "Hora por confirmar", className: "scheduled" };
}
function matchCard(match, showDate = false) {
  const status = matchStatus(match);
  const hasScore = match.homeScore !== null && match.homeScore !== undefined && match.awayScore !== null && match.awayScore !== undefined;
  const stopped = ["cancelled", "postponed", "suspended"].includes(match.status);
  const statusDescription = stopped ? (match.cancellationReason || match.statusText || "FotMob no indica el motivo del cambio de estado.") : match.status === "live" ? (match.statusText || "Partido en curso") : match.status === "finished" ? (match.statusText || "Tiempo completo") : (match.round ? `Jornada ${match.round}` : "");
  const kickoff = `${showDate ? `${fmtShortDate(match.date)} · ` : ""}${match.time || "Hora por confirmar"}`;
  return `<article class="match-card ${stopped ? "match-stopped" : ""}"><div class="match-top"><span class="match-time">${esc(kickoff)}</span><span class="state ${status.className}">${status.className === "live" ? `<i></i>` : ""}${status.label}</span></div><div class="team-line"><div class="team-name">${teamImage(match.homeId, match.home)}<span>${esc(match.home)}</span></div><span class="score ${hasScore ? "" : "muted"}">${hasScore ? esc(match.homeScore) : "—"}</span></div><div class="team-line"><div class="team-name">${teamImage(match.awayId, match.away)}<span>${esc(match.away)}</span></div><span class="score ${hasScore ? "" : "muted"}">${hasScore ? esc(match.awayScore) : "—"}</span></div>${stopped ? `<div class="match-explanation"><b>Motivo</b><span>${esc(statusDescription)}</span></div>` : `<div class="match-bottom"><span>${esc(statusDescription)}</span><span>${match.round ? `Jornada ${esc(match.round)}` : ""}</span></div>`}</article>`;
}
function renderMatches(league) {
  const games = (league?.matches || []).filter((match) => match.date === state.date).sort((a, b) => (a.time || "").localeCompare(b.time || ""));
  $("#match-count").textContent = `${games.length} ${games.length === 1 ? "partido" : "partidos"}`;
  $("#selected-date-label").textContent = fmtDate(state.date);
  $("#match-date").value = state.date;
  $("#match-list").innerHTML = games.length ? games.map((match) => matchCard(match)).join("") : `<div class="empty-state"><span class="empty-ball">⚽</span><b>No hay partidos este día</b><span>Prueba con otra fecha del calendario de ${esc(league?.name || "la liga")}.</span></div>`;
}
function renderUpcoming(league) {
  const today = madridDate();
  const now = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Madrid", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date());
  const upcoming = (league?.matches || []).filter((match) => {
    if (!(match.status === "scheduled" || match.status === "postponed") || !match.date || match.date < today) return false;
    return match.date > today || !match.time || match.time >= now;
  }).sort((a, b) => `${a.date} ${a.time || "23:59"}`.localeCompare(`${b.date} ${b.time || "23:59"}`)).slice(0, 6);
  $("#upcoming-count").textContent = `${upcoming.length} ${upcoming.length === 1 ? "partido" : "partidos"}`;
  $("#upcoming-list").innerHTML = upcoming.length ? upcoming.map((match) => matchCard(match, true)).join("") : `<div class="empty-state"><span class="empty-ball">⚽</span><b>No hay próximos partidos disponibles</b><span>FotMob no muestra más encuentros programados para esta temporada.</span></div>`;
}
function zoneFor(league, row) {
  const position = Number(row.rank) - 1;
  for (const zone of league.legend || []) {
    if (!(zone.indices || []).map(Number).includes(position)) continue;
    const title = zone.title.toLocaleLowerCase("es-ES");
    if (title.includes("champions") && title.includes("qualification")) return { label: "Champions (previa)", key: "champions-qualifier", color: zone.color };
    if (title.includes("champions")) return { label: "Champions", key: "champions", color: zone.color };
    if (title.includes("conference")) return { label: "Conference", key: "conference", color: zone.color };
    if (title.includes("europa")) return { label: "Europa League", key: "europa", color: zone.color };
    if ((title.includes("relegation") || title.includes("descenso")) && title.includes("qualification")) return { label: "Play-off descenso", key: "playoff", color: zone.color };
    if (title.includes("relegation") || title.includes("descenso")) return { label: "Descenso", key: "relegation", color: zone.color };
  }
  return { label: "", key: "", color: "" };
}
function renderStandings(league) {
  const rows = league?.standings || [];
  if (!rows.length) {
    $("#standings").innerHTML = `<div class="table-empty">No hay clasificación disponible.</div>`;
    $("#zone-legend").innerHTML = "";
    return;
  }
  const categories = new Map();
  const html = rows.map((row, index) => {
    const zone = zoneFor(league, row);
    if (zone.key) categories.set(zone.key, zone);
    const leader = index === 0;
    const label = leader ? (zone.label ? `Líder · ${zone.label}` : "Líder") : zone.label;
    // FotMob incluye el color de clasificación de cada fila. Priorizarlo evita
    // desplazar plazas cuando una liga añade rondas o puestos europeos extra.
    // El líder lleva un marcador dorado propio aunque también clasifique a Champions.
    const markerColor = leader ? "#f1c84b" : (row.qualColor || zone.color || "transparent");
    return `<div class="standing-row ${zone.key ? `zone-${zone.key}` : ""} ${leader ? "is-leader" : ""}" style="--zone-color:${esc(markerColor)}" title="${esc(label || "")}"><span class="rank-cell">${esc(row.rank)}</span><span class="standing-club">${teamImage(row.id, row.name, true)}<span>${esc(row.shortName || row.name)}</span></span><span>${esc(row.played)}</span><span class="goal-diff ${Number(row.gd) > 0 ? "positive" : Number(row.gd) < 0 ? "negative" : ""}">${Number(row.gd) > 0 ? "+" : ""}${esc(row.gd)}</span><b class="points-cell">${esc(row.points)}</b></div>`;
  }).join("");
  $("#standings").innerHTML = html;
  const order = ["champions", "champions-qualifier", "conference", "europa", "playoff", "relegation"];
  const entries = order.map((key) => categories.get(key)).filter(Boolean);
  const leaderLegend = `<span><i style="--zone-color:#f1c84b"></i>Líder</span>`;
  $("#zone-legend").innerHTML = leaderLegend + entries.map((zone) => `<span><i style="--zone-color:${esc(zone.color || "#65756b")}"></i>${esc(zone.label)}</span>`).join("");
}
function renderTitleOdds(league) {
  const teams = (league?.titleOdds || []).slice(0, 3);
  const source = league?.titleOddsSource;
  const note = $("#title-odds-note");
  if (source?.updatedAt) {
    const stamp = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid" }).format(new Date(source.updatedAt));
    const simulations = Number(source.simulations || 0).toLocaleString("es-ES");
    note.innerHTML = `Fuente: <a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.name || "Footyntel")}</a> · ${simulations} simulaciones · Actualizado ${stamp} · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>`;
  } else {
    note.textContent = "Pronóstico externo no disponible en este momento.";
  }
  $("#title-odds-list").innerHTML = teams.length ? teams.map((team) => {
    const chance = Math.max(0, Math.min(100, Number(team.probability) || 0));
    return `<div class="title-odds-row"><div class="title-odds-team">${teamImage(team.id, team.name, true)}<span>${esc(team.name)}</span></div><b class="title-odds-value">${chance.toFixed(1).replace(".", ",")}%</b><div class="title-odds-track"><i style="width:${chance}%"></i></div></div>`;
  }).join("") : `<div class="title-odds-empty">Pronóstico externo todavía no disponible.</div>`;
}
function renderLeaders(target, players, valueLabel) {
  if (!players?.length) {
    $(target).innerHTML = `<div class="leader-empty">Estadística aún no disponible.</div>`;
    return;
  }
  $(target).innerHTML = players.slice(0, 5).map((player, index) => {
    const safeId = String(player.id ?? "").replace(/[^\d]/g, "");
    const teamId = String(player.teamId ?? "").replace(/[^\d]/g, "");
    return `<div class="leader-row"><span class="leader-rank">${String(index + 1).padStart(2, "0")}</span><span class="player-photo-wrap">${safeId ? `<img class="player-photo" src="${playerPhoto(safeId)}" alt="Foto de ${esc(player.name)}" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false">` : ""}<span class="player-fallback" ${safeId ? "hidden" : ""}>${esc(initials(player.name))}</span></span><span class="player-info"><b>${esc(player.name)}</b><small>${teamId ? `<img class="player-team-logo" src="${teamLogo(teamId)}" alt="" onerror="this.hidden=true">` : ""}${esc(player.team)}</small></span><strong class="player-total">${esc(player.value)}<small>${valueLabel}</small></strong></div>`;
  }).join("");
}
function renderAll() {
  if (state.data?.leagues?.length && !state.data.leagues.some((league) => Number(league.id) === state.leagueId)) {
    state.leagueId = Number(state.data.leagues[0].id);
  }
  const league = activeLeague();
  if (!league) return;
  renderLeagueNav();
  renderHeader(league);
  renderMatches(league);
  renderUpcoming(league);
  renderStandings(league);
  renderTitleOdds(league);
  renderLeaders("#top-scorers", league.scorers, "goles");
  renderLeaders("#top-assists", league.assists, "asist.");
  const dates = (league.matches || []).map((match) => match.date).filter(Boolean).sort();
  if (dates.length) {
    $("#match-date").min = dates[0];
    $("#match-date").max = dates.at(-1);
  }
}
async function refresh() {
  if (state.loading) return;
  state.loading = true;
  try {
    const localMode = location.hostname === "localhost" || location.hostname === "127.0.0.1";
    const response = await fetch(localMode ? "/api/football" : `data/football.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Respuesta HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.error) throw new Error(payload.error);
    state.data = payload;
    renderAll();
    const stamp = payload.updatedAt ? new Date(payload.updatedAt) : new Date();
    $("#updated-at").textContent = `Datos ${new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid" }).format(stamp)}`;
    const message = $("#message");
    message.className = "message success-message";
    message.textContent = `Calendarios, clasificaciones y líderes actualizados automáticamente. Última sincronización ${new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid" }).format(stamp)}.`;
  } catch (error) {
    const message = $("#message");
    message.className = "message error-message";
    message.textContent = `No se pudieron actualizar los datos: ${error.message}. La API de FotMob es no oficial y puede cambiar o rechazar solicitudes.`;
  } finally {
    state.loading = false;
  }
}

$("#prev-day").addEventListener("click", () => {
  const date = new Date(`${state.date}T12:00:00`);
  date.setDate(date.getDate() - 1);
  state.date = madridDate(date);
  renderAll();
});
$("#next-day").addEventListener("click", () => {
  const date = new Date(`${state.date}T12:00:00`);
  date.setDate(date.getDate() + 1);
  state.date = madridDate(date);
  renderAll();
});
$("#today-button").addEventListener("click", () => { state.date = madridDate(); renderAll(); });
$("#match-date").addEventListener("change", (event) => { if (event.target.value) { state.date = event.target.value; renderAll(); } });
$("#refresh").addEventListener("click", refresh);
refresh();
setInterval(refresh, 60_000);
