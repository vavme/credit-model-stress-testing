// Small hand-written SVG chart helpers. No libraries. Colours: one accent, greys for context.
import { esc, int } from "./data.js";

export const C = { acc: "#2a78d6", accInk: "#1c5cab", accSoft: "#e8f1fc", grey: "#8a929b", greyDark: "#5f6872", ink: "#1f2933", ink2: "#4b5563", grid: "#e3e6ea", missing: "#5f6872" };
const NS = "http://www.w3.org/2000/svg";
const CHAR_W = 6.5; // approx px per character at 12.5px

export function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}
export function txt(parent, x, y, s, attrs = {}) {
  const t = el("text", { x, y, "font-size": 12.5, ...attrs }, parent);
  t.textContent = s;
  return t;
}
export function wrap(s, maxChars) {
  const words = String(s).split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > maxChars && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur);
  return lines;
}
export function niceMax(v) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
export function fmtAxis(v) {
  if (Math.abs(v) >= 1000) return v.toLocaleString("en-US");
  return String(Math.round(v * 100) / 100);
}
export function width(c, min = 300) { return Math.max(min, Math.floor(c.getBoundingClientRect().width || c.clientWidth || 600)); }

// Redraw when the container width changes.
export function responsive(c, draw) {
  let last = -1;
  const run = () => {
    const w = width(c);
    if (Math.abs(w - last) < 24) return;
    last = w;
    draw(w);
  };
  run();
  if (window.ResizeObserver) new ResizeObserver(run).observe(c);
  else window.addEventListener("resize", run);
}

// ---------------------------------------------------------------- tooltip
let tipEl = null;
export function tip(node, html) {
  tipEl = tipEl || document.getElementById("tip");
  if (!window.__tipInit) {
    window.__tipInit = true;
    ["scroll", "touchstart", "click"].forEach((ev) => window.addEventListener(ev, () => { const t = document.getElementById("tip"); if (t) t.style.display = "none"; }, { passive: true, capture: true }));
  }
  const show = (e) => {
    if (!tipEl) return;
    tipEl.innerHTML = html;
    tipEl.style.display = "block";
    const x = (e.clientX ?? node.getBoundingClientRect().left) + 14;
    const y = (e.clientY ?? node.getBoundingClientRect().top) + 14;
    const w = tipEl.offsetWidth;
    tipEl.style.left = Math.min(x, window.innerWidth - w - 8) + "px";
    tipEl.style.top = Math.min(y, window.innerHeight - tipEl.offsetHeight - 8) + "px";
  };
  const hide = () => { if (tipEl) tipEl.style.display = "none"; };
  node.addEventListener("mouseenter", show);
  node.addEventListener("mousemove", show);
  node.addEventListener("mouseleave", hide);
  node.addEventListener("focus", show);
  node.addEventListener("blur", hide);
}

function root(w, h, label) {
  const s = el("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, role: "img", "aria-label": label });
  return s;
}
function mount(c, svg) { c.querySelectorAll(":scope > svg").forEach((n) => n.remove()); c.appendChild(svg); }

// ---------------------------------------------------------------- horizontal bars
// rows: {label, value, hi (accent), note, tip}
export function barsH(c, rows, o = {}) {
  const w = o.w || width(c);
  const narrow = w < 520;
  const labW = o.labelW || Math.min(narrow ? Math.floor(w * 0.42) : 230, Math.max(...rows.map((r) => r.label.length)) * CHAR_W);
  const maxChars = Math.max(8, Math.floor(labW / CHAR_W));
  const valW = o.valW || 92;
  const barMax = w - labW - valW - 16;
  const max = o.max || niceMax(Math.max(...rows.map((r) => r.value)));
  let y = 4;
  const items = rows.map((r) => { const lines = wrap(r.label, maxChars); const h = Math.max(26, lines.length * 15 + 8); const it = { r, lines, y, h }; y += h; return it; });
  const svg = root(w, y + 4, o.aria || "Bar chart");
  for (const { r, lines, y: y0, h } of items) {
    const cy = y0 + h / 2;
    lines.forEach((ln, i) => txt(svg, labW, cy - ((lines.length - 1) * 7.5) + i * 15 + 4.5, ln, { "text-anchor": "end", fill: r.hi ? C.ink : C.ink2, "font-weight": r.hi ? 700 : 400 }));
    const bw = Math.max(1, (r.value / max) * barMax);
    const bar = el("rect", { x: labW + 8, y: cy - 8, width: bw, height: 16, rx: 3, fill: r.hi ? C.acc : C.grey }, svg);
    txt(svg, labW + 8 + bw + 6, cy + 4.5, o.fmt ? o.fmt(r) : String(r.value), { fill: C.ink, "font-weight": r.hi ? 700 : 400 });
    if (r.tip) tip(bar, r.tip);
  }
  mount(c, svg);
}

// ---------------------------------------------------------------- vertical bars (with optional intervals and n)
// rows: {label, value|null, n, lo, hi, kind: 'normal'|'missing', tip, short}
export function barsV(c, rows, o = {}) {
  const w = o.w || width(c);
  const left = 46, right = 8, top = 22;
  const k = rows.length;
  const bw = (w - left - right) / k;
  const rotate = o.showN && bw < 40;
  const bottom = (o.showN ? (rotate ? 50 : 34) : 8) + 24;
  const h = o.h || 250;
  const ph = h - top - bottom;
  const vals = rows.map((r) => (r.hi ?? r.value ?? 0));
  const max = o.max || niceMax((Math.max(...vals, o.overall || 0) * 1.05) / 4) * 4;
  const svg = root(w, h, o.aria || "Bar chart");
  const yOf = (v) => top + ph - (v / max) * ph;
  for (let i = 0; i <= 4; i++) {
    const v = (max / 4) * i;
    el("line", { x1: left, x2: w - right, y1: yOf(v), y2: yOf(v), stroke: C.grid }, svg);
    txt(svg, left - 6, yOf(v) + 4, (o.axisFmt ? o.axisFmt(v) : fmtAxis(v)), { "text-anchor": "end", "font-size": 11.5 });
  }
  if (o.overall != null) {
    el("line", { x1: left, x2: w - right, y1: yOf(o.overall), y2: yOf(o.overall), stroke: C.ink2, "stroke-dasharray": "4 3" }, svg);
  }
  const gap = Math.min(6, bw * 0.18);
  rows.forEach((r, i) => {
    const x = left + i * bw + gap / 2, bwid = bw - gap;
    const cx = x + bwid / 2;
    if (r.value == null) {
      el("rect", { x, y: yOf(0) - 3, width: bwid, height: 3, fill: C.grid }, svg);
      txt(svg, cx, yOf(0) - 8, "<" + (o.minCell || 10), { "text-anchor": "middle", "font-size": 10.5 });
    } else {
      const fill = r.kind === "missing" ? C.missing : (o.color || C.acc);
      const bar = el("rect", { x, y: yOf(r.value), width: bwid, height: Math.max(1, yOf(0) - yOf(r.value)), fill, rx: 2 }, svg);
      if (r.tip) tip(bar, r.tip);
      if (r.lo != null && r.hi != null) {
        el("line", { x1: cx, x2: cx, y1: yOf(r.lo), y2: yOf(r.hi), stroke: C.ink, "stroke-width": 1.3 }, svg);
        for (const v of [r.lo, r.hi]) el("line", { x1: cx - 3, x2: cx + 3, y1: yOf(v), y2: yOf(v), stroke: C.ink, "stroke-width": 1.3 }, svg);
      }
      if (o.valueLabels === "all" || (o.valueLabels === "ends" && (o.labelIdx || []).includes(i))) {
        txt(svg, cx, yOf(r.hi ?? r.value) - 5, o.valFmt ? o.valFmt(r.value) : fmtAxis(r.value), { "text-anchor": "middle", "font-size": 11, fill: C.ink, "font-weight": 700 });
      }
    }
    const every = o.labelEvery || 1;
    if (i % every === 0 || i === k - 1) {
      txt(svg, cx, yOf(0) + 15, r.short ?? r.label, { "text-anchor": "middle", "font-size": 11.5 });
    }
    if (o.showN && r.n != null) {
      const t = txt(svg, cx, yOf(0) + 30, int(r.n), { "text-anchor": rotate ? "end" : "middle", "font-size": 10.5, fill: C.greyDark });
      if (rotate) t.setAttribute("transform", `rotate(-90 ${cx + 3} ${yOf(0) + 30})`);
    }
  });
  if (o.showN) txt(svg, left - 6, yOf(0) + 30, "n", { "text-anchor": "end", "font-size": 10.5, fill: C.greyDark });
  mount(c, svg);
}

// ---------------------------------------------------------------- waffle
export function waffle(c, d, F) {
  const { filled, of } = d.charts.waffle;
  c.innerHTML = "";
  const box = document.createElement("div");
  box.className = "wf";
  c.appendChild(box);
  const size = Math.min(26, Math.floor((Math.min(width(c), 560) * 0.5 - 12) / 10) - 3);
  const gap = 3, W = 10 * (size + gap);
  const svg = el("svg", { viewBox: `0 0 ${W} ${W}`, width: W, height: W, role: "img", "aria-label": `${filled} of ${of} squares filled, one square per hundred loans` });
  for (let i = 0; i < of; i++) {
    const row = Math.floor(i / 10), col = i % 10;
    el("rect", { x: col * (size + gap), y: row * (size + gap), width: size, height: size, rx: 3, fill: i < filled ? C.acc : "#dde1e6" }, svg);
  }
  box.appendChild(svg);
  const t = document.createElement("div");
  t.className = "wf-text";
  t.innerHTML = `<p class="big"><strong>${esc(F("default_rate_pct"))}</strong> of loans have payment trouble<br><span class="muted">${esc(F("n_pos"))} of ${esc(F("n_train"))} loans. Each square is one in every ${esc(F("waffle_total"))} loans.</span></p>
  <p class="callout-inline">Approve everyone and flag no one: <strong>${esc(F("acc_all_zero_pct"))}</strong> accurate, and it finds none of the ${esc(F("n_pos"))} loans with trouble.</p>`;
  box.appendChild(t);
}

// ---------------------------------------------------------------- dumbbell: present vs missing
export function dumbbell(c, d, F) {
  const rows = d.charts.dumbbell;
  responsive(c, (w) => {
    const narrow = w < 560;
    const labW = narrow ? Math.floor(w * 0.4) : 250;
    const maxChars = Math.floor(labW / CHAR_W);
    const maxX = 12;
    const x0 = labW + 10, xW = w - x0 - (narrow ? 10 : 150);
    const xOf = (v) => x0 + (v / maxX) * xW;
    let y = 28;
    const rowH = narrow ? 64 : 50;
    const svg = root(w, 28 + rows.length * rowH + 44, "Default rate when a value is present and when it is missing, by column family");
    for (let t = 0; t <= maxX; t += 2) {
      el("line", { x1: xOf(t), x2: xOf(t), y1: 14, y2: 28 + rows.length * rowH, stroke: C.grid }, svg);
      txt(svg, xOf(t), 28 + rows.length * rowH + 16, t + "%", { "text-anchor": "middle", "font-size": 11.5 });
    }
    txt(svg, x0 + xW / 2, 28 + rows.length * rowH + 36, "Default rate", { "text-anchor": "middle", "font-size": 12 });
    const overall = parseFloat(F("default_rate_pct"));
    el("line", { x1: xOf(overall), x2: xOf(overall), y1: 14, y2: 28 + rows.length * rowH, stroke: C.ink2, "stroke-dasharray": "4 3" }, svg);
    txt(svg, xOf(overall), 10, "all loans " + F("default_rate_pct"), { "text-anchor": "middle", "font-size": 11.5, fill: C.ink2 });
    rows.forEach((r, i) => {
      const cy = y + rowH / 2 - 4;
      const lines = wrap(r.family, maxChars);
      lines.forEach((ln, j) => txt(svg, labW, cy - (lines.length - 1) * 7 + j * 14 + 1, ln, { "text-anchor": "end", fill: C.ink, "font-weight": 600 }));
      txt(svg, labW, cy + (lines.length - 1) * 7 + 15, r.missing_pct.toFixed(1) + "% missing", { "text-anchor": "end", "font-size": 11.5, fill: C.greyDark });
      if (narrow && r.gap_pp < 0) txt(svg, labW, cy + (lines.length - 1) * 7 + 29, "Reversed: pensioner effect", { "text-anchor": "end", "font-size": 11.5, fill: C.ink });
      const a = xOf(r.rate_present), b = xOf(r.rate_missing);
      el("line", { x1: a, x2: b, y1: cy, y2: cy, stroke: C.grey, "stroke-width": 3 }, svg);
      if (r.range_missing) el("line", { x1: xOf(r.range_missing[0]), x2: xOf(r.range_missing[1]), y1: cy + 12, y2: cy + 12, stroke: C.acc, "stroke-width": 2 }, svg);
      const dp = el("circle", { cx: a, cy, r: 7, fill: C.greyDark, stroke: "#fff", "stroke-width": 2 }, svg);
      const dm = el("circle", { cx: b, cy, r: 7, fill: C.acc, stroke: "#fff", "stroke-width": 2 }, svg);
      tip(dp, `<b>${esc(r.family)}</b><br>Value present: ${r.rate_present.toFixed(2)}%`);
      tip(dm, `<b>${esc(r.family)}</b><br>Value missing: ${r.rate_missing.toFixed(2)}%`);
      const left = Math.min(a, b), right = Math.max(a, b);
      const presentLeft = a < b;
      txt(svg, (presentLeft ? left : right) + (presentLeft ? -12 : 12), cy + 4.5, r.rate_present.toFixed(2) + "%", { "text-anchor": presentLeft ? "end" : "start", "font-size": 11.5, fill: C.greyDark });
      txt(svg, (presentLeft ? right : left) + (presentLeft ? 12 : -12), cy + 4.5, r.rate_missing.toFixed(2) + "%", { "text-anchor": presentLeft ? "start" : "end", "font-size": 11.5, fill: C.accInk, "font-weight": 700 });
      if (r.gap_pp < 0 && !narrow) txt(svg, w - 4, cy + 4.5, "Reversed: mostly the pensioner effect", { "text-anchor": "end", "font-size": 11.5, fill: C.ink });
      y += rowH;
    });
    mount(c, svg);
    let key = c.querySelector(".keyrow");
    if (!key) { key = document.createElement("div"); key.className = "keyrow"; key.innerHTML = `<span style="--k:${C.greyDark}">Value present</span><span style="--k:${C.acc}">Value missing</span><span>Blue line under the building row shows the range across its patterns</span>`; c.appendChild(key); }
  });
}

// ---------------------------------------------------------------- heatmap of co-missingness
export function heatmap(c, d) {
  const H = d.charts.heatmap, n = H.labels.length;
  c.innerHTML = '<p class="subtitle"><strong>Which missing patterns occur together</strong> (phi correlation, darker means missing together more often)</p>';
  const holder = document.createElement("div");
  c.appendChild(holder);
  responsive(holder, (w) => {
    const left = 30, top = 22;
    const cell = Math.max(9, Math.min(26, Math.floor((w - left - 8) / n)));
    const size = left + n * cell + 8;
    const svg = root(size, top + n * cell + 6, "Heatmap of how often the missing patterns occur together");
    const mix = (v) => { const a = [232, 241, 252], b = [28, 92, 171]; return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * v)).join(",")})`; };
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const r = el("rect", { x: left + j * cell, y: top + i * cell, width: cell - 1, height: cell - 1, fill: mix(Math.max(0, H.phi[i][j])) }, svg);
      tip(r, `${esc(H.labels[i])} and ${esc(H.labels[j])}<br>phi ${H.phi[i][j].toFixed(2)}`);
    }
    for (let i = 0; i < n; i++) if (cell >= 14 || i % 2 === 0) {
      txt(svg, left + i * cell + cell / 2, top - 6, String(i + 1), { "text-anchor": "middle", "font-size": 10 });
      txt(svg, left - 4, top + i * cell + cell / 2 + 3.5, String(i + 1), { "text-anchor": "end", "font-size": 10 });
    }
    holder.querySelectorAll(":scope > svg").forEach((x) => x.remove());
    holder.prepend(svg);
    if (!holder.querySelector("ol")) {
      const ol = document.createElement("ol");
      ol.className = "muted";
      ol.style.cssText = "columns:2 260px;font-size:13px;margin-top:8px";
      ol.innerHTML = H.labels.map((l) => `<li>${esc(l)}</li>`).join("");
      holder.appendChild(ol);
    }
  });
}

export function patternsTable(c, d) {
  const rows = d.charts.patterns;
  c.innerHTML = `<p class="subtitle"><strong>All missing patterns above the threshold</strong></p><table><thead><tr><th>#</th><th>Columns</th><th>Group</th><th>Missing</th><th>Default rate when missing</th><th>When present</th><th>Gap (points)</th></tr></thead><tbody>${rows.map((r, i) => `<tr><td>${i + 1}</td><td>${esc(r.label)}</td><td>${esc(r.group)}</td><td>${r.missing_pct.toFixed(2)}%</td><td>${r.rate_missing.toFixed(2)}%</td><td>${r.rate_present.toFixed(2)}%</td><td>${r.gap_pp > 0 ? "+" : ""}${r.gap_pp.toFixed(2)}</td></tr>`).join("")}</tbody></table>`;
}

// ---------------------------------------------------------------- distribution of one feature (explorer)
export function distChart(c, rec) {
  const dist = rec.dist;
  if (dist.kind === "none") { c.innerHTML = '<p class="muted">No statistics are shown for an identifier.</p>'; return; }
  if (dist.kind === "hist") {
    const rows = dist.counts.map((n, i) => ({ label: String(dist.edges[i]), short: "", n, value: n, tip: `${fmtAxis(dist.edges[i])} to ${fmtAxis(dist.edges[i + 1])}: ${int(n)} loans` }));
    responsive(c, (w) => {
      barsV(c, rows, { w, h: 200, color: C.grey, aria: "Histogram of " + rec.name, labelEvery: 99 });
      const svg = c.querySelector("svg");
      const left = 46, plot = w - left - 8;
      [0, 0.5, 1].forEach((f) => { const v = dist.edges[0] + (dist.edges[dist.edges.length - 1] - dist.edges[0]) * f; txt(svg, left + plot * f, 200 - 14, fmtAxis(v), { "text-anchor": f === 0 ? "start" : f === 1 ? "end" : "middle", "font-size": 11.5 }); });
    });
    const note = [];
    if (dist.below || dist.above) note.push(`The chart covers the middle of the values. ${int(dist.below)} loans fall below it and ${int(dist.above)} above it.`);
    if (dist.n_missing) note.push(`${int(dist.n_missing)} loans have no value.`);
    if (dist.n_placeholder) note.push(`${int(dist.n_placeholder)} loans hold the placeholder value and are left out of the chart.`);
    c.insertAdjacentHTML("beforeend", `<p class="chart-note">${note.join(" ")}</p>`);
    return;
  }
  const rows = dist.rows.map((r) => ({ label: r.label, value: r.n, tip: `${esc(r.label)}: ${int(r.n)} loans` }));
  if (dist.n_missing) rows.push({ label: "(missing)", value: dist.n_missing });
  if (rows.length > 8 || dist.kind === "cats") barsH(c, rows, { aria: "Counts for " + rec.name, fmt: (r) => int(r.value), labelW: 200 });
  else responsive(c, (w) => barsV(c, rows.map((r) => ({ ...r, n: null })), { w, h: 200, color: C.grey, valueLabels: "all", valFmt: (v) => int(v), aria: "Counts for " + rec.name }));
}

// ---------------------------------------------------------------- default rate by bin with intervals (explorer, story)
export function rateChart(c, rec, overall, opts = {}) {
  const bins = rec.rate_bins;
  if (!bins.length) { c.innerHTML = '<p class="muted">No default-rate breakdown for this column.</p>'; return; }
  const rows = bins.map((b, i) => ({ label: b.label, short: bins.length > 12 ? "" : (b.label === "missing" ? "NA" : (rec.dist.kind === "hist" || /^\(/.test(b.label) ? String(i + 1) : b.label.slice(0, 9))), value: b.rate, lo: b.lo, hi: b.hi, n: b.n,
    kind: b.label === "missing" ? "missing" : "normal", tip: `<b>${esc(b.label)}</b><br>${int(b.n)} loans<br>${b.rate == null ? "Under 10 loans, rate hidden" : "Default rate " + b.rate.toFixed(2) + "%" + (b.lo != null ? " (95% range " + b.lo.toFixed(2) + " to " + b.hi.toFixed(2) + ")" : "")}` }));
  if (bins.length > 12) {
    const sorted = rows.filter((r) => r.value != null).sort((a, b) => b.n - a.n);
    barsH(c, sorted.map((r) => ({ label: `${r.label} (n ${int(r.n)})`, value: r.value, hi: false, tip: r.tip })), { aria: "Default rate by " + rec.name, fmt: (r) => r.value.toFixed(2) + "%", labelW: 240, max: Math.max(...sorted.map((r) => r.value)) * 1.1 });
    return;
  }
  const numericBins = /^\(/.test(bins[0].label);
  c.querySelectorAll(".dashkey").forEach((n) => n.remove());
  c.insertAdjacentHTML("beforeend", `<p class="chart-note dashkey">Dashed line: default rate of all loans, ${overall.toFixed(2)}%.${bins.some((b) => b.label === "missing") ? " NA, grey bar: loans where the value is missing." : ""}</p>`);
  responsive(c, (w) => barsV(c, rows, { w, h: 270, showN: true, overall, overallLabel: "all loans " + overall.toFixed(2) + "%", axisFmt: (v) => v.toFixed(0) + "%", valueLabels: opts.valueLabels || (rows.length <= 11 ? "all" : "ends"), valFmt: (v) => v.toFixed(1), aria: "Default rate by " + (numericBins ? "decile" : "value") + " of " + rec.name, color: opts.color || C.acc }));
}

// ---------------------------------------------------------------- tables as text alternatives
export function binTable(rec) {
  if (!rec.rate_bins.length) return "";
  return `<table><thead><tr><th>Bin</th><th>Loans</th><th>Default rate</th><th>95% range</th></tr></thead><tbody>${rec.rate_bins.map((b) => `<tr><td>${esc(b.label)}</td><td>${int(b.n)}</td><td>${b.rate == null ? "under 10 loans" : b.rate.toFixed(2) + "%"}</td><td>${b.lo == null ? "" : b.lo.toFixed(2) + " to " + b.hi.toFixed(2)}</td></tr>`).join("")}</tbody></table>`;
}
