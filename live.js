const $ = (selector) => document.querySelector(selector);
const state = { matches: [], activeLeague: "Todas", loading: false };
const today = new Intl.DateTimeFormat("es-ES", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Madrid" }).format(new Date());
$("#today-date").textContent = today.charAt(0).toUpperCase() + today.slice(1);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const initials = (name) => String(name || "?").split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
const crest = (team, id) => id ? `<img class="crest" loading="lazy" src="https://images.fotmob.com/image_resources/logo/teamlogo/${encodeURIComponent(id)}.png" alt="" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'crest-placeholder',textContent:'${esc(initials(team))}'}))">` : `<span class="crest-placeholder" aria-hidden="true">${esc(initials(team))}</span>`;
function statusText(match) {
  if (match.status === "live") return match.minute ? `EN JUEGO · ${esc(match.minute)}` : "EN JUEGO";
  if (match.status === "finished") return "FINALIZADO";
  if (match.status === "cancelled") return "CANCELADO";
  return esc(match.time || "Hora por confirmar");
}
function render() {
  const matches = state.activeLeague === "Todas" ? state.matches : state.matches.filter((item) => item.league === state.activeLeague);
  const grouped = new Map();
  for (const match of matches) { if (!grouped.has(match.league)) grouped.set(match.league, []); grouped.get(match.league).push(match); }
  const target = $("#match-list");
  if (!matches.length) { target.innerHTML = `<div class="empty">No hay partidos disponibles${state.activeLeague !== "Todas" ? ` para ${esc(state.activeLeague)}` : ""} en esta fecha.</div>`; return; }
  target.innerHTML = [...grouped].map(([league, games]) => `<section class="league-section"><h2 class="league-heading">${games[0].leagueLogo ? `<img class="league-logo" src="https://images.fotmob.com/image_resources/logo/leaguelogo/${encodeURIComponent(games[0].leagueLogo)}.png" alt="" onerror="this.remove()">` : ""}${esc(league)}</h2><div class="match-list">${games.map((match) => {
    const hasScore = match.homeScore !== null && match.homeScore !== undefined;
    const scoreHome = hasScore ? esc(match.homeScore) : "—";
    const scoreAway = hasScore ? esc(match.awayScore) : "—";
    return `<article class="match-card"><div class="match-top"><span>${esc(match.time || "")}</span><span class="state ${esc(match.status)}">${statusText(match)}</span></div><div class="team-line"><div class="team-name">${crest(match.home, match.homeId)}<span>${esc(match.home)}</span></div><span class="score ${hasScore ? "" : "muted"}">${scoreHome}</span></div><div class="team-line"><div class="team-name">${crest(match.away, match.awayId)}<span>${esc(match.away)}</span></div><span class="score ${hasScore ? "" : "muted"}">${scoreAway}</span></div><div class="match-bottom"><span>${esc(match.statusText || (match.status === "finished" ? "Tiempo completo" : ""))}</span><span class="round">${esc(match.round || "")}</span></div></article>`;
  }).join("")}</div></section>`).join("");
}
function renderFilters() {
  const leagues = ["Todas", ...new Set(state.matches.map((match) => match.league))];
  const container = $("#league-filters");
  if (!leagues.includes(state.activeLeague)) state.activeLeague = "Todas";
  container.innerHTML = leagues.map((league) => `<button class="filter ${league === state.activeLeague ? "active" : ""}" type="button" data-league="${esc(league)}">${esc(league)}</button>`).join("");
  container.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => { state.activeLeague = button.dataset.league; renderFilters(); render(); }));
}
async function refresh() {
  if (state.loading) return;
  state.loading = true;
  const message = $("#message");
  try {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
    const date = `${parts.find((part) => part.type === "year").value}-${parts.find((part) => part.type === "month").value}-${parts.find((part) => part.type === "day").value}`;
    const localMode = location.hostname === "localhost" || location.hostname === "127.0.0.1";
    const url = localMode ? `/api/matches?date=${date}` : `data/today.json?ts=${Date.now()}`;
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Respuesta HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.error) throw new Error(payload.error);
    state.matches = Array.isArray(payload.matches) ? payload.matches : [];
    renderFilters(); render();
    const stamp = payload.updatedAt ? new Date(payload.updatedAt) : new Date();
    $("#updated-at").textContent = `Datos actualizados ${new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Madrid" }).format(stamp)}`;
    message.className = "message";
    message.textContent = location.hostname.endsWith("github.io") ? "Los resultados se consultan en FotMob y esta copia pública se renueva automáticamente cada pocos minutos." : "Actualización automática cada 60 segundos.";
  } catch (error) {
    message.className = "message error";
    message.textContent = `No se pudieron actualizar los partidos: ${error.message}. FotMob es una fuente no oficial y puede cambiar o rechazar solicitudes.`;
    if (!state.matches.length) $("#match-list").innerHTML = `<div class="empty">No hay datos disponibles ahora mismo. Vuelve a intentarlo en unos minutos.</div>`;
  } finally { state.loading = false; }
}
$("#refresh").addEventListener("click", refresh);
refresh();
setInterval(refresh, 60_000);
