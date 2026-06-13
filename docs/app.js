/* WM 2026 ShredBotSoccer Agent – Frontend-Logik (kein Build, keine Dependencies) */

const ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard";
const LIVE_INTERVAL_MS = 30000;
const TZ = "Europe/Zurich";

const state = { predictions: null, byId: {}, liveTimer: null };

/* ---------- Helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const pct = (x) => Math.round((x || 0) * 100);

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("de-CH", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
}
function fmtDateLong(iso) {
  const d = iso ? new Date(iso + "T12:00:00Z") : new Date();
  return d.toLocaleDateString("de-CH", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: TZ });
}
const _ymdFmt = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });
function ymd(offsetDays = 0) {
  return _ymdFmt.format(new Date(Date.now() + offsetDays * 86400000)).replace(/-/g, "");
}
function zurichYMD(iso) {
  return _ymdFmt.format(new Date(iso)).replace(/-/g, "");
}
function todayYMD() {
  return ymd(0);
}

/* Fetch JSON mit CORS-Fallback über öffentliche Proxys (nur für ESPN nötig) */
async function getJSON(url, useProxyFallback = false) {
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch (e) {
    if (!useProxyFallback) throw e;
    const proxies = [
      (u) => `https://corsproxy.io/?url=${encodeURIComponent(u)}`,
      (u) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
    ];
    for (const p of proxies) {
      try {
        const r = await fetch(p(url), { cache: "no-store" });
        if (r.ok) return await r.json();
      } catch (_) { /* nächster Proxy */ }
    }
    throw e;
  }
}

/* ---------- Tabs ---------- */
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => switchTab(t.dataset.tab));
});
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === name));
  if (name === "live") startLive();
  if (name === "results") loadResults();
}

/* ---------- Vor dem Spiel ---------- */
async function loadPredictions() {
  const box = $("#preCards");
  box.innerHTML = '<div class="skeleton"></div>'.repeat(3);
  try {
    const data = await getJSON("data/predictions/latest.json");
    state.predictions = data;
    data.matches.forEach((m) => (state.byId[m.id] = m));

    $("#subline").textContent = fmtDateLong(data.date) + " · " + data.count + " Spiel(e)";
    if (data.generated_at) {
      $("#updated").innerHTML = "Tipps erstellt:<br>" +
        new Date(data.generated_at).toLocaleString("de-CH", { dateStyle: "medium", timeStyle: "short", timeZone: TZ });
    }
    const mode = data.matches.some((m) => m.enriched_by === "claude") ? "Modell + Recherche" : "Modell (Basis)";
    $("#preTitle").textContent = "Tipps des Tages — " + mode;
    renderPre();
    // hält die "gespielt"-Dimmung aktuell, auch wenn die Seite offen bleibt
    if (!state.preTimer) state.preTimer = setInterval(renderPre, 60000);
  } catch (e) {
    box.innerHTML = emptyHTML("⚠️", "Tipps konnten nicht geladen werden.<br><small>" + e + "</small>");
  }
}

function renderPre() {
  const data = state.predictions;
  if (!data) return;
  const box = $("#preCards");
  box.innerHTML = "";
  if (!data.matches.length) {
    box.innerHTML = emptyHTML("📅", "Heute keine WM-Spiele angesetzt.");
    return;
  }
  // noch anstehende Spiele zuerst (voll), bereits gespielte danach (kompakt & gedimmt)
  const now = Date.now();
  const sorted = data.matches
    .map((m) => ({ m, played: new Date(m.kickoff_utc).getTime() < now }))
    .sort((a, b) => (a.played - b.played) || (new Date(a.m.kickoff_utc) - new Date(b.m.kickoff_utc)));
  sorted.forEach(({ m, played }) => box.appendChild(predCard(m, played)));
}

function predCard(m, played = false) {
  const p = m.prediction, pr = p.prob;
  const c = el("div", played ? "card played" : "card");

  c.appendChild(el("div", "meta",
    `<span class="group-badge">${m.group ? "Gruppe " + m.group : "K.o."}</span>
     <span>${played ? "✓ gespielt" : (m.venue ? m.venue + " · " : "") + (m.city || "")}</span>`));

  c.appendChild(el("div", "match", `
    ${teamHTML(m.home)}
    <div class="center">
      <div class="kickoff">${fmtTime(m.kickoff_utc)}</div>
      <div class="score">${p.scoreline}</div>
      <div class="vs">Tipp</div>
    </div>
    ${teamHTML(m.away)}`));

  c.appendChild(el("div", "probbar", `
    <i class="h" style="width:${pct(pr.home)}%"></i>
    <i class="d" style="width:${pct(pr.draw)}%"></i>
    <i class="a" style="width:${pct(pr.away)}%"></i>`));
  c.appendChild(el("div", "problabels", `
    <span><b>${pct(pr.home)}%</b> ${m.home.code}</span>
    <span><b>${pct(pr.draw)}%</b> Remis</span>
    <span><b>${pct(pr.away)}%</b> ${m.away.code}</span>`));

  const winLabel = p.winner_code
    ? `${p.winner} <small>siegt</small>`
    : `Unentschieden`;
  const confLabel = { Hoch: "Hohe", Mittel: "Mittlere", Niedrig: "Niedrige" }[p.confidence] || p.confidence;
  c.appendChild(el("div", "tip", `
    <span class="winner">🏆 ${winLabel}</span>
    <span class="conf ${p.confidence}">${confLabel} Konfidenz</span>`));

  if (m.rationale_de) c.appendChild(el("p", "rationale", m.rationale_de));

  if (m.key_factors && m.key_factors.length) {
    const f = el("div", "factors");
    m.key_factors.forEach((k) => f.appendChild(el("span", null, k)));
    c.appendChild(f);
  }

  c.appendChild(el("div", "stats", `
    <div><b>${p.expected_goals.home} : ${p.expected_goals.away}</b>xG (erw. Tore)</div>
    <div><b>${pct(p.over_2_5)}%</b>Über 2.5</div>
    <div><b>${pct(p.btts)}%</b>Beide treffen</div>`));

  if (m.odds_snapshot && m.odds_snapshot.moneyline) {
    const o = m.odds_snapshot;
    c.appendChild(el("div", "odds",
      `📊 Quoten (${o.provider || "Buchmacher"}): <b>${o.moneyline.home}</b> / <b>${o.moneyline.draw}</b> / <b>${o.moneyline.away}</b>`));
  }
  return c;
}

function teamHTML(t) {
  return `<div class="team">
    <img src="${t.logo || ""}" alt="${t.code}" loading="lazy"
         onerror="this.style.visibility='hidden'"/>
    <span class="tname">${t.name}</span>
    ${t.elo ? `<span class="elo">Elo ${Math.round(t.elo)}</span>` : ""}
  </div>`;
}

/* ---------- Live Games ---------- */
async function startLive() {
  if (state.liveTimer) return; // schon aktiv
  await refreshLive();
  state.liveTimer = setInterval(refreshLive, LIVE_INTERVAL_MS);
}

async function refreshLive() {
  const box = $("#liveCards");
  if (!box.children.length) box.innerHTML = '<div class="skeleton"></div>'.repeat(2);
  let events;
  try {
    // Fenster gestern–morgen: ESPN bucketet nach US-Ostküsten-Datum, daher kann ein
    // nachts (CEST) laufendes Spiel im Vortags-Bucket liegen.
    const data = await getJSON(`${ESPN}?dates=${ymd(-1)}-${ymd(1)}&limit=100`, true);
    events = data.events || [];
  } catch (e) {
    box.innerHTML = emptyHTML("⚠️", "Live-Daten gerade nicht erreichbar.<br><small>Neuer Versuch in 30 s.</small>");
    return;
  }

  const order = { in: 0, pre: 1, post: 2 };
  const today = todayYMD();
  // alle laufenden Spiele + alle Spiele des heutigen Zürcher Tages (anstehend/beendet)
  const games = events.map(normLive)
    .filter((g) => g.state === "in" || zurichYMD(g.date) === today)
    .sort((a, b) => (order[a.state] - order[b.state]) || a.date.localeCompare(b.date));

  const liveN = games.filter((g) => g.state === "in").length;
  $("#liveCount").textContent = liveN || "";

  box.innerHTML = "";
  if (!games.length) {
    box.innerHTML = emptyHTML("🌙", "Heute keine WM-Spiele.");
    return;
  }
  games.forEach((g) => box.appendChild(liveCard(g)));
}

function normLive(e) {
  const comp = (e.competitions || [{}])[0];
  const cs = comp.competitors || [];
  const home = cs.find((c) => c.homeAway === "home") || cs[0] || {};
  const away = cs.find((c) => c.homeAway === "away") || cs[1] || {};
  const st = (e.status || {}).type || {};
  return {
    id: e.id, date: e.date, state: st.state, status: st.shortDetail || st.description,
    clock: (e.status || {}).displayClock,
    home: liveTeam(home), away: liveTeam(away),
  };
}
function liveTeam(c) {
  const t = c.team || {};
  return { code: t.abbreviation, name: t.displayName, logo: t.logo, score: c.score };
}

function liveCard(g) {
  const c = el("div", "card");
  const chip = g.state === "in"
    ? `<span class="statuschip in"><span class="livedot"></span> ${g.status || "Live"}</span>`
    : g.state === "post"
      ? `<span class="statuschip post">Beendet</span>`
      : `<span class="statuschip pre">${fmtTime(g.date)}</span>`;
  c.appendChild(el("div", "meta", `<span>${g.id ? "WM 2026" : ""}</span>${chip}`));

  const sc = (g.state === "pre") ? "–" : `${g.home.score ?? 0} : ${g.away.score ?? 0}`;
  c.appendChild(el("div", "match", `
    ${teamHTML(g.home)}
    <div class="center"><div class="score">${sc}</div>
      <div class="vs">${g.state === "in" ? (g.clock || "live") : g.state === "post" ? "Endstand" : "Anstoss"}</div>
    </div>
    ${teamHTML(g.away)}`));

  // Abgleich mit Morgen-Tipp
  const tip = state.byId[g.id];
  if (tip && g.state !== "pre") {
    c.appendChild(trackHTML(tip, g));
  }
  return c;
}

function trackHTML(tip, g) {
  const hs = +g.home.score, as = +g.away.score;
  const actual = hs > as ? "home" : hs < as ? "away" : "draw";
  const predicted = tip.prediction.winner_code === g.home.code ? "home"
    : tip.prediction.winner_code === g.away.code ? "away" : "draw";
  const ok = actual === predicted;
  const verb = g.state === "post" ? (ok ? "Tipp ist aufgegangen" : "Tipp daneben") : (ok ? "Tipp liegt vorn" : "Tipp hinten");
  return el("div", "track",
    `Tipp war <b>${tip.prediction.winner} ${tip.prediction.scoreline}</b> · ` +
    `<span class="${ok ? "ok" : "no"}">${ok ? "✓" : "✗"} ${verb}</span>`);
}

/* ---------- Resultate & Trefferquote ---------- */
const GROUP_ORDER = "ABCDEFGHIJKL";

async function loadResults() {
  const box = $("#resultsGroups");
  if (!box.children.length) box.innerHTML = '<div class="skeleton"></div>';
  await refreshResults();
  // hält die Resultate aktuell: neue Spiele erscheinen, sobald sie abgepfiffen sind
  if (!state.resultsTimer) state.resultsTimer = setInterval(refreshResults, 60000);
}

async function refreshResults() {
  const sum = $("#resultsSummary"), box = $("#resultsGroups");
  let archive, events;
  try {
    // Tipp-Archiv (statisch) + beendete Spiele live von ESPN
    [archive, events] = await Promise.all([
      getJSON("data/predictions/archive.json"),
      getJSON(`${ESPN}?dates=20260611-20260719&limit=400`, true).then((d) => d.events || []),
    ]);
  } catch (e) {
    // Fallback: vorberechnete results.json (vom Tageslauf)
    try {
      const data = await getJSON("data/results.json");
      sum.innerHTML = data.count ? resultSummary(data) : "";
      box.innerHTML = "";
      (data.groups || []).forEach((g) => box.appendChild(resultGroup(g)));
    } catch (_) {
      sum.innerHTML = "";
      box.innerHTML = emptyHTML("📊", "Resultate gerade nicht erreichbar.<br><small>" + e + "</small>");
    }
    return;
  }

  const data = buildResults(archive, events);
  if (!data.count) {
    sum.innerHTML = "";
    box.innerHTML = emptyHTML("⏳", "Noch keine WM-Spiele abgeschlossen.<br><small>Sobald die ersten Partien gespielt sind, erscheint hier die Trefferquote.</small>");
    return;
  }
  sum.innerHTML = resultSummary(data);
  box.innerHTML = "";
  data.groups.forEach((g) => box.appendChild(resultGroup(g)));
}

function buildResults(archive, events) {
  const graded = [];
  for (const e of events) {
    const st = (e.status || {}).type || {};
    if (st.state !== "post") continue;
    const comp = (e.competitions || [{}])[0];
    const cs = comp.competitors || [];
    const home = cs.find((c) => c.homeAway === "home") || cs[0] || {};
    const away = cs.find((c) => c.homeAway === "away") || cs[1] || {};
    const hs = parseInt(home.score, 10), as = parseInt(away.score, 10);
    if (Number.isNaN(hs) || Number.isNaN(as)) continue;
    const tip = archive[e.id];
    if (!tip) continue; // kein Tipp archiviert -> nicht bewertbar
    const g = gradeClient(tip, hs, as);
    graded.push({
      date_utc: e.date, group: tip.group,
      home: tip.home, away: tip.away,
      actual: `${hs}:${as}`,
      tip: { winner: tip.prediction.winner, scoreline: tip.prediction.scoreline,
             confidence: tip.prediction.confidence, prob: tip.prediction.prob },
      result_score: g.score, factors: g.factors, verdict: g.verdict,
    });
  }

  const buckets = {};
  graded.forEach((m) => (buckets[m.group || "K.o.-Runde"] ||= []).push(m));
  Object.values(buckets).forEach((v) => v.sort((a, b) => a.date_utc.localeCompare(b.date_utc)));
  const gkey = (k) => (GROUP_ORDER.includes(k) ? GROUP_ORDER.indexOf(k) : 99);
  const groups = Object.keys(buckets).sort((a, b) => gkey(a) - gkey(b) || a.localeCompare(b))
    .map((k) => ({ group: k, matches: buckets[k] }));

  const n = graded.length;
  const sum = graded.reduce((s, m) => s + m.result_score, 0);
  return {
    count: n,
    overall_quote: n ? Math.round((sum / n) * 10) / 10 : 0,
    tendency_rate: n ? Math.round(100 * graded.filter((m) => m.factors.tendenz).length / n) : 0,
    exact_rate: n ? Math.round(100 * graded.filter((m) => m.factors.exakt).length / n) : 0,
    groups,
  };
}

// identische Trefferquoten-Formel wie engine/results.py
function gradeClient(tip, hs, as) {
  const actual = hs > as ? "home" : hs < as ? "away" : "draw";
  const [ph, pa] = tip.prediction.scoreline.split(":").map(Number);
  const predOut = tip.prediction.winner_code === tip.home.code ? "home"
    : tip.prediction.winner_code === tip.away.code ? "away" : "draw";
  const tendenz = predOut === actual;
  const tordiff = (ph - pa) === (hs - as);
  const exakt = ph === hs && pa === as;
  const probActual = (tip.prediction.prob && tip.prediction.prob[actual]) || 0;
  let score = (tendenz ? 50 : 0) + (tordiff ? 20 : 0) + (exakt ? 20 : 0) + 10 * probActual;
  score = Math.min(100, Math.round(score * 10) / 10);
  const verdict = exakt ? "Volltreffer" : (tendenz && tordiff) ? "Tendenz + Tordifferenz"
    : tendenz ? "Tendenz richtig" : "Daneben";
  return { score, verdict, factors: { tendenz, tordifferenz: tordiff, exakt, prob_actual: Math.round(probActual * 1000) / 1000 } };
}

function resultSummary(d) {
  const q = d.overall_quote;
  return `<div class="quote-card">
    <div class="quote-main">
      <div class="quote-num ${scoreClass(q)}">${q}%</div>
      <div class="quote-label">Gesamt-Trefferquote<br><small>${d.count} bewertete Spiele</small></div>
    </div>
    <div class="quote-bar"><i class="${scoreClass(q)}" style="width:${q}%"></i></div>
    <div class="quote-sub">
      <span><b>${d.tendency_rate}%</b> Tendenz richtig</span>
      <span><b>${d.exact_rate}%</b> exaktes Resultat</span>
    </div>
    <div class="quote-legend">Punkte je Spiel: Tendenz +50 · Tordifferenz +20 · exakt +20 · Modell-Überzeugung +0–10</div>
  </div>`;
}

function resultGroup(g) {
  const wrap = el("div", "result-group");
  wrap.appendChild(el("h3", "group-title", g.group.length === 1 ? "Gruppe " + g.group : g.group));
  const cards = el("div", "cards");
  g.matches.forEach((m) => cards.appendChild(resultCard(m)));
  wrap.appendChild(cards);
  return wrap;
}

function resultCard(m) {
  const c = el("div", "card");
  const f = m.factors;
  c.appendChild(el("div", "meta", `
    <span>${fmtResultDate(m.date_utc)}</span>
    <span class="score-badge ${scoreClass(m.result_score)}">${m.result_score}%</span>`));

  c.appendChild(el("div", "match", `
    ${teamHTML(m.home)}
    <div class="center"><div class="score">${m.actual}</div><div class="vs">Endstand</div></div>
    ${teamHTML(m.away)}`));

  c.appendChild(el("div", "result-tip", `
    <span>Tipp: <b>${m.tip.winner === "Unentschieden" ? "Remis" : m.tip.winner} ${m.tip.scoreline}</b></span>
    <span class="verdict ${scoreClass(m.result_score)}">${m.verdict}</span>`));

  const chips = el("div", "factors");
  chips.appendChild(el("span", f.tendenz ? "ok" : "no", (f.tendenz ? "✓" : "✗") + " Tendenz"));
  chips.appendChild(el("span", f.tordifferenz ? "ok" : "no", (f.tordifferenz ? "✓" : "✗") + " Tordifferenz"));
  chips.appendChild(el("span", f.exakt ? "ok" : "no", (f.exakt ? "✓" : "✗") + " Exakt"));
  chips.appendChild(el("span", null, "Modell gab " + pct(f.prob_actual) + "%"));
  c.appendChild(chips);
  return c;
}

function fmtResultDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("de-CH", { day: "numeric", month: "short", timeZone: TZ });
}

function scoreClass(s) {
  return s >= 90 ? "s-top" : s >= 70 ? "s-good" : s >= 50 ? "s-mid" : "s-low";
}

/* ---------- Empty ---------- */
function emptyHTML(icon, msg) {
  return `<div class="empty"><span class="big">${icon}</span>${msg}</div>`;
}

/* ---------- Init ---------- */
loadPredictions();
