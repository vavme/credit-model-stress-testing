// Renders the charts of the story page and the section navigation.
import { BASE, esc, int } from "./data.js";
import { C, barsH, barsV, dumbbell, el, heatmap, niceMax, patternsTable, rateChart, responsive, txt, tip, waffle, width, wrap, fmtAxis } from "./charts.js";

export function initStory(d, F) {
  const overall = parseFloat(F("default_rate_pct"));

  // Draw the charts of a section only when it is close to the screen. This keeps the first load light.
  const sections = [...document.querySelectorAll("section.story")];
  const run = (s) => {
    if (s.dataset.done) return;
    s.dataset.done = "1";
    renderCharts(new Set([...s.querySelectorAll("[data-chart]")].map((e) => e.dataset.chart)));
  };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { run(e.target); io.unobserve(e.target); } }), { rootMargin: "900px 0px" });
    sections.forEach((s) => io.observe(s));
  } else sections.forEach(run);
  initNav();

  function renderCharts(names) {
  const q = (name) => (names.has(name) ? document.querySelector(`[data-chart="${name}"]`) : null);

  // ---- 2: groups and types
  const groups = q("groups");
  if (groups) {
    const rows = d.charts.groups.map((g) => ({ label: g.group, value: g.n, hi: g.group.startsWith("Building"), tip: `${esc(g.group)}: ${g.n} columns` }));
    responsive(groups, (w) => barsH(groups, rows, { w, aria: "Number of columns per feature group", fmt: (r) => String(r.value) + (r.hi ? " columns" : ""), valW: 100 }));
  }
  const types = q("types");
  if (types) {
    const total = d.charts.types.reduce((a, t) => a + t.n, 0);
    const shades = ["#4b5563", "#6b7280", "#8a929b", "#a6adb5", "#c3c8ce", "#d7dbe0", "#e8ebee"];
    types.innerHTML = `<p class="subtitle"><strong>The same columns by type</strong></p>`;
    const holder = document.createElement("div");
    types.appendChild(holder);
    responsive(holder, (w) => {
      const svg = el("svg", { viewBox: `0 0 ${w} 26`, width: w, height: 26, role: "img", "aria-label": "Columns by type: " + d.charts.types.map((t) => `${t.type} ${t.n}`).join(", ") });
      let x = 0;
      d.charts.types.forEach((t, i) => { const sw = (t.n / total) * w; const r = el("rect", { x, y: 0, width: Math.max(1, sw - 2), height: 26, fill: shades[i % shades.length], rx: 3 }, svg); tip(r, `${esc(t.type)}: ${t.n}`); x += sw; });
      holder.querySelectorAll(":scope > svg").forEach((n) => n.remove());
      holder.prepend(svg);
    });
    const ul = document.createElement("p");
    ul.className = "chart-note";
    ul.textContent = d.charts.types.map((t) => `${t.n} ${t.type}`).join(" | ");
    types.appendChild(ul);
  }

  // ---- 3: waffle
  const wf = q("waffle");
  if (wf) waffle(wf, d, F);

  // ---- 4: missing data
  const db = q("dumbbell");
  if (db) dumbbell(db, d, F);
  const mg = q("missing_groups");
  if (mg) {
    const rows = d.charts.missing_by_group.filter((g) => g.with_missing > 0).sort((a, b) => b.mean_missing_pct - a.mean_missing_pct)
      .map((g) => ({ label: g.group, value: g.mean_missing_pct, hi: g.group.startsWith("Building"), tip: `${esc(g.group)}: ${g.with_missing} of ${g.columns} columns have missing values` }));
    mg.innerHTML = '<p class="subtitle"><strong>Average missing share by group</strong> (across all columns of the group)</p>';
    const holder = document.createElement("div");
    mg.appendChild(holder);
    responsive(holder, (w) => barsH(holder, rows, { w, max: 100, aria: "Average missing share by feature group", fmt: (r) => r.value.toFixed(1) + "%" }));
  }
  const hm = q("heatmap");
  if (hm) heatmap(hm, d);
  const pt = q("patterns_table");
  if (pt) patternsTable(pt, d);

  // ---- 5: signal master-detail
  const sig = q("signal");
  if (sig) {
    const byName = Object.fromEntries(d.features.map((f) => [f.name, f]));
    const top = d.charts.signal_top;
    sig.innerHTML = `<div class="md"><ul class="mdlist" aria-label="Choose a feature"></ul><div><p class="mdtitle"></p><div class="mdchart"></div><p class="chart-note mdnote"></p></div></div>`;
    const list = sig.querySelector(".mdlist"), title = sig.querySelector(".mdtitle"), chart = sig.querySelector(".mdchart"), note = sig.querySelector(".mdnote");
    let current = "EXT_SOURCE_3";
    const draw = () => {
      const rec = byName[current];
      title.innerHTML = `<strong>${esc(current)}</strong> <span class="muted">(${esc(rec.group)})</span><br>Default rate in each decile, lowest values to highest`;
      rateChart(chart, rec, overall);
      note.innerHTML = `Highest bin minus lowest bin: <strong>${rec.range_pp.toFixed(2)}</strong> points. With shuffled labels the same gap is about ${rec.null_range_pp.toFixed(2)} points. The number of loans in each bin is printed under each bar.`;
      list.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.f === current ? "true" : "false"));
    };
    top.forEach((t) => {
      const li = document.createElement("li");
      li.innerHTML = `<button type="button" data-f="${esc(t.feature)}" aria-pressed="false">${esc(t.feature)}<span class="r">range ${t.range_pp.toFixed(2)} points</span></button>`;
      li.querySelector("button").addEventListener("click", () => { current = t.feature; draw(); });
      list.appendChild(li);
    });
    draw();
  }

  // ---- 6: DAYS_EMPLOYED histogram with placeholder bar
  const de = q("days_employed");
  if (de) {
    const H = d.charts.days_employed_hist;
    responsive(de, (w) => {
      const h = 260, left = 58, right = 8, top = 16, bottom = 52;
      const ph = h - top - bottom, plotW = w - left - right;
      const k = H.counts.length;
      const slot = plotW / (k + 5);
      const max = niceMax(Math.max(H.placeholder_n, ...H.counts) * 1.04);
      const yOf = (v) => top + ph - (v / max) * ph;
      const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, role: "img", "aria-label": `Histogram of years in the current job. A separate bar holds the ${int(H.placeholder_n)} rows with the placeholder value.` });
      for (let i = 0; i <= 4; i++) { const v = (max / 4) * i; el("line", { x1: left, x2: w - right, y1: yOf(v), y2: yOf(v), stroke: C.grid }, svg); txt(svg, left - 6, yOf(v) + 4, fmtAxis(v), { "text-anchor": "end", "font-size": 11.5 }); }
      H.counts.forEach((n, i) => { const r = el("rect", { x: left + i * slot + 1, y: yOf(n), width: slot - 2, height: Math.max(1, yOf(0) - yOf(n)), fill: C.grey }, svg); tip(r, `${H.edges_years[i].toFixed(1)} to ${H.edges_years[i + 1].toFixed(1)} years: ${int(n)} loans`); });
      const px = left + (k + 3) * slot;
      const pb = el("rect", { x: px, y: yOf(H.placeholder_n), width: slot * 2 - 2, height: yOf(0) - yOf(H.placeholder_n), fill: C.acc }, svg);
      tip(pb, `Placeholder ${F("sentinel_value")}: ${int(H.placeholder_n)} loans`);
      const lo = H.edges_years[0], hi = H.edges_years[H.edges_years.length - 1];
      for (let yr = 0; yr <= hi; yr += 10) txt(svg, left + ((yr - lo) / (hi - lo)) * (k * slot), yOf(0) + 16, String(yr), { "text-anchor": "middle", "font-size": 11.5 });
      txt(svg, left + (k * slot) / 2, yOf(0) + 34, "Years in current job (real values)", { "text-anchor": "middle", "font-size": 12 });
      txt(svg, px + slot, yOf(0) + 16, String(F("sentinel_value")), { "text-anchor": "middle", "font-size": 11.5, fill: C.accInk, "font-weight": 700 });
      txt(svg, px + slot, yOf(0) + 34, "placeholder", { "text-anchor": "middle", "font-size": 12, fill: C.accInk });
      const lines = wrap(`${F("sentinel_n")} rows (${F("sentinel_pct")}) hold the placeholder, not a real job length`, Math.max(14, Math.floor((px - left - 20) / 6.5)));
      lines.forEach((ln, i) => txt(svg, px - 10, yOf(H.placeholder_n) + 12 + i * 15, ln, { "text-anchor": "end", fill: C.ink, "font-weight": 700 }));
      de.querySelectorAll(":scope > svg").forEach((n) => n.remove());
      de.appendChild(svg);
    });
  }

  // ---- 7: shortlist matrix, list, exclusions
  const mx = q("matrix");
  if (mx) {
    const rows = d.charts.shortlist_matrix;
    const order = d.charts.groups.map((g) => g.group);
    const cap = document.getElementById("matrix-caption");
    mx.innerHTML = "";
    const keyHtml = `<div class="keyrow" aria-hidden="true"><span class="k k-sl">Proposed</span><span class="k k-rl">Proposed, needs a ruling</span><span class="k k-op">Excluded, could return</span><span class="k k-ex">Excluded</span></div>`;
    const wrap_ = document.createElement("div");
    wrap_.setAttribute("aria-hidden", "true");
    order.forEach((g) => {
      const m = rows.filter((r) => r.group === g);
      const kept = m.filter((r) => r.status === "shortlist" || r.status === "shortlist_ruling").length;
      const blk = document.createElement("div");
      blk.className = "mgroup";
      blk.innerHTML = `<div class="mlabel">${esc(g)} <span class="muted">(${kept} of ${m.length} proposed)</span></div>`;
      const sq = document.createElement("div");
      sq.className = "squares";
      m.forEach((r) => {
        const b = document.createElement("button");
        b.type = "button"; b.tabIndex = -1;
        b.className = "sq s-" + r.status;
        b.setAttribute("aria-label", r.name);
        tip(b, `<b>${esc(r.name)}</b><br>${esc(r.reason)}`);
        b.addEventListener("click", () => {
          const label = { shortlist: "Proposed", shortlist_ruling: "Proposed, needs a ruling", option: "Excluded, could return", excluded: "Excluded" }[r.status];
          cap.innerHTML = `<strong>${esc(r.name)}</strong>: ${label}. ${esc(r.reason)} <a href="${BASE}explorer.html?feature=${encodeURIComponent(r.name)}">Open in the Feature Explorer</a>`;
        });
        sq.appendChild(b);
      });
      blk.appendChild(sq);
      wrap_.appendChild(blk);
    });
    mx.appendChild(wrap_);
    mx.insertAdjacentHTML("beforeend", keyHtml);
  }
  const sl = q("shortlist_list");
  if (sl) {
    const order = d.charts.groups.map((g) => g.group);
    const rows = d.charts.shortlist_matrix.filter((r) => r.status === "shortlist" || r.status === "shortlist_ruling");
    sl.innerHTML = `<table><thead><tr><th>Group</th><th>Column</th><th>Why a bank would care</th></tr></thead><tbody>${order.flatMap((g) => rows.filter((r) => r.group === g)).map((r) => `<tr><td>${esc(r.group)}</td><td><a href="${BASE}explorer.html?feature=${encodeURIComponent(r.name)}">${esc(r.name)}</a>${r.status === "shortlist_ruling" ? ' <span class="pill rl">needs a ruling</span>' : ""}</td><td>${esc(r.reason)}</td></tr>`).join("")}</tbody></table>`;
  }
  const ex = q("exclusions");
  if (ex) {
    const opts = d.charts.shortlist_matrix.filter((r) => r.status === "option");
    ex.innerHTML = `<p class="subtitle"><strong>Excluded, but could return if the author decides so</strong></p><table><thead><tr><th>Column</th><th>Why it is out for now</th></tr></thead><tbody>${opts.map((r) => `<tr><td><a href="${BASE}explorer.html?feature=${encodeURIComponent(r.name)}">${esc(r.name)}</a></td><td>${esc(r.reason)}</td></tr>`).join("")}</tbody></table>
    <p class="subtitle"><strong>Other exclusions by reason</strong></p><table><thead><tr><th>Reason</th><th>Columns</th></tr></thead><tbody>${d.charts.exclusion_reasons.map((r) => `<tr><td>${esc(r.reason)}</td><td>${r.n}</td></tr>`).join("")}</tbody></table>`;
  }

  // ---- 8: candidates
  const cd = q("candidates");
  if (cd) {
    const rows = [...d.charts.candidates].sort((a, b) => a.rank - b.rank);
    const dots = (rank) => `<svg width="104" height="22" viewBox="0 0 104 22" role="img" aria-label="Draft damage rank ${rank} of 5">${[1, 2, 3, 4, 5].map((i) => `<circle cx="${10 + (i - 1) * 21}" cy="11" r="7" fill="${i === rank ? C.acc : "#fff"}" stroke="${i === rank ? C.acc : C.grey}" stroke-width="2"/>`).join("")}</svg>`;
    cd.innerHTML = `<p class="chart-note" style="margin:0 0 8px">Draft damage rank at the highest severity: 1 is the largest damage, 5 the smallest. "Today" shows the clean state of the data.</p><table class="plain-table cand"><thead><tr><th scope="col">Candidate</th><th scope="col">Scenario</th><th scope="col">Draft damage rank</th><th scope="col">Draft prediction</th><th scope="col">What would prove it wrong</th></tr></thead><tbody>${rows.map((r) => `<tr class="${r.slug === "labels" ? "hl" : ""}"><th scope="row">${esc(r.target)}<div class="muted" style="font-weight:400">${esc(r.failure)}</div></th><td><span class="pill">${esc(r.scenario)}</span> ${esc(r.scenario_name)}</td><td>${dots(r.rank)}<div class="muted">rank ${r.rank}</div></td><td><span class="muted">Today:</span> ${esc(r.clean)}<br><strong>Prediction:</strong> ${esc(r.prediction)} <span class="muted">Confidence: ${esc(r.confidence)}.</span></td><td>${esc(r.falsifier)}</td></tr>`).join("")}</tbody></table>`;
  }

  // ---- 9: roadmap
  const rm = q("roadmap");
  if (rm) {
    rm.innerHTML = `<ol class="roadmap">${d.charts.roadmap.map((p) => `<li class="${p.state}"><span class="ph">Phase ${p.phase}${p.state === "done" ? ", done" : p.state === "next" ? ", next" : ""}</span>${esc(p.title)}</li>`).join("")}</ol>`;
  }

  }
}

function initNav() {
  const bar = document.getElementById("progressbar");
  const links = [...document.querySelectorAll(".navlinks a[data-sec]")];
  const onScroll = () => {
    const h = document.documentElement.scrollHeight - window.innerHeight;
    if (bar && h > 0) bar.style.width = Math.min(100, (window.scrollY / h) * 100) + "%";
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  const secs = links.map((a) => document.getElementById(a.dataset.sec)).filter(Boolean);
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          links.forEach((a) => a.classList.toggle("active", a.dataset.sec === e.target.id));
          const act = links.find((a) => a.dataset.sec === e.target.id);
          const nav = document.querySelector(".navlinks");
          if (act && nav && nav.scrollWidth > nav.clientWidth) nav.scrollTo({ left: act.offsetLeft - nav.clientWidth / 2 + act.clientWidth / 2 });
        }
      });
    }, { rootMargin: "-30% 0px -60% 0px" });
    secs.forEach((s) => io.observe(s));
  }
}
