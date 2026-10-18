// Feature Explorer: filter the table, open a detail view. State lives in the URL.
import { BASE, esc, int } from "./data.js";
import { binTable, distChart, rateChart } from "./charts.js";

const STATUS = {
  shortlist: ["Proposed", "sl"], shortlist_ruling: ["Proposed, needs a ruling", "rl"],
  option: ["Excluded, could return", "op"], excluded: ["Excluded", ""],
};

export function initExplorer(d, F) {
  const feats = d.features;
  const overall = parseFloat(F("default_rate_pct"));
  const $ = (id) => document.getElementById(id);
  const sel = { search: $("f-search"), group: $("f-group"), type: $("f-type"), missing: $("f-missing"), shortlist: $("f-shortlist"), sort: $("f-sort"), flag: $("f-flag") };

  const opts = (el, values, first) => { el.innerHTML = `<option value="">${first}</option>` + values.map((v) => `<option>${esc(v)}</option>`).join(""); };
  opts(sel.group, [...new Set(feats.map((f) => f.group))], "Any");
  opts(sel.type, [...new Set(feats.map((f) => f.type))], "Any");

  // read the URL
  const p = new URLSearchParams(location.search);
  const set = (el, v) => { if (v == null) return; if ([...el.options || []].some((o) => o.value === v || o.text === v) || el.tagName === "INPUT") el.value = v; };
  set(sel.search, p.get("search")); set(sel.group, p.get("group")); set(sel.type, p.get("type"));
  set(sel.missing, p.get("missing_min")); set(sel.shortlist, p.get("shortlist")); set(sel.sort, p.get("sort"));
  set(sel.flag, p.get("flag") || (p.get("candidate") === "yes" ? "candidate" : null));
  let selected = p.get("feature");

  const quirkful = (f) => f.quirks.some((q) => q.tag !== "NOTE");
  const matches = (f) => {
    const s = sel.search.value.trim().toLowerCase();
    if (s && !(f.name.toLowerCase().includes(s) || (f.description || "").toLowerCase().includes(s))) return false;
    if (sel.group.value && f.group !== sel.group.value) return false;
    if (sel.type.value && f.type !== sel.type.value) return false;
    if (sel.missing.value && !(f.missing_pct > parseFloat(sel.missing.value))) return false;
    const sl = sel.shortlist.value;
    if (sl === "yes" && !(f.shortlist === "shortlist" || f.shortlist === "shortlist_ruling")) return false;
    if (sl === "option" && f.shortlist !== "option") return false;
    if (sl === "no" && f.shortlist !== "excluded") return false;
    const fl = sel.flag.value;
    if (fl === "quirk" && !quirkful(f)) return false;
    if (fl === "sensitive" && !f.sensitive) return false;
    if (fl === "candidate" && !f.candidate) return false;
    return true;
  };

  const syncUrl = () => {
    const q = new URLSearchParams();
    if (sel.search.value) q.set("search", sel.search.value);
    if (sel.group.value) q.set("group", sel.group.value);
    if (sel.type.value) q.set("type", sel.type.value);
    if (sel.missing.value) q.set("missing_min", sel.missing.value);
    if (sel.shortlist.value) q.set("shortlist", sel.shortlist.value);
    if (sel.sort.value) q.set("sort", sel.sort.value);
    if (sel.flag.value) q.set("flag", sel.flag.value);
    if (selected) q.set("feature", selected);
    history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q : ""));
  };

  const renderTable = () => {
    let rows = feats.filter(matches);
    const s = sel.sort.value;
    if (s === "range_pp") rows.sort((a, b) => (b.range_pp ?? -1) - (a.range_pp ?? -1));
    else if (s === "missing_pct") rows.sort((a, b) => b.missing_pct - a.missing_pct);
    else if (s === "name") rows.sort((a, b) => a.name.localeCompare(b.name));
    $("count").textContent = `Showing ${rows.length} of ${feats.length} columns.`;
    $("ex-body").innerHTML = rows.map((f) => {
      const [label, cls] = STATUS[f.shortlist];
      return `<tr class="row${f.name === selected ? " sel" : ""}" data-n="${esc(f.name)}"><td><button type="button" class="name" data-n="${esc(f.name)}">${esc(f.name)}</button></td><td>${esc(f.group)}</td><td>${esc(f.type)}</td><td>${f.missing_pct ? f.missing_pct.toFixed(2) + "%" : "none"}</td><td>${f.range_pp != null ? f.range_pp.toFixed(2) + " pts" : ""}</td><td><span class="pill ${cls}">${label}</span></td></tr>`;
    }).join("") || `<tr><td colspan="6">No column matches these filters.</td></tr>`;
    syncUrl();
  };

  const detail = $("detail");
  const renderDetail = () => {
    const f = feats.find((x) => x.name === selected);
    if (!f) { detail.innerHTML = '<p class="muted">Select a column in the table to see its details.</p>'; return; }
    const [label, cls] = STATUS[f.shortlist];
    const draftLabel = d.site.ai_draft_adopted ? d.site.ai_adopted_label : d.site.ai_draft_label;
    const draftClass = d.site.ai_draft_adopted ? "authorlabel" : "draftlabel";
    const desc = f.description ? esc(f.description) : "No description written yet.";
    detail.innerHTML = `
      <h2>${esc(f.name)}</h2>
      <div class="meta"><span class="pill">${esc(f.group)}</span><span class="pill">${esc(f.type)}</span><span class="pill ${cls}">${label}</span>${f.sensitive ? '<span class="pill">Sensitive attribute</span>' : ""}${f.candidate ? '<span class="pill op">Corruption candidate (draft)</span>' : ""}</div>
      <p>${desc} <span class="muted">(${esc(d.site.desc_label)})</span></p>
      <p><strong>Missing:</strong> ${f.missing_pct ? f.missing_pct.toFixed(2) + "%" : "none"}. <strong>Distinct values:</strong> ${int(f.n_unique)}. <strong>Stored as:</strong> ${esc(f.dtype)}.${f.notes ? " <strong>Notes:</strong> " + esc(f.notes) + "." : ""}</p>
      <div class="grid2">
        <div><h3>How the values are spread</h3><div id="d-dist"></div></div>
        <div><h3>Default rate across the values</h3><div id="d-rate"></div>
          <details class="chart-details"><summary>Show as a table</summary><div class="scrollx">${binTable(f)}</div></details></div>
      </div>
      ${f.quirks.length ? "<h3>Quirks and risk flags</h3>" + f.quirks.map((q) => `<div class="quirk ${q.tag === "HYPOTHESIS" ? "hyp" : q.tag === "DATA" ? "data" : ""}"><span class="tag tag-${q.tag === "HYPOTHESIS" ? "hyp" : q.tag === "DATA" ? "data" : "doc"}">${q.tag === "HYPOTHESIS" ? "Hypothesis" : q.tag === "DATA" ? "Data" : "Note"}</span> ${esc(q.text)}</div>`).join("") : ""}
      <h3>Shortlist status</h3>
      <span class="${draftClass}">${esc(draftLabel)}</span>
      <p><strong>${label}.</strong> ${esc(f.shortlist_reason)}</p>
      <p class="source">All figures: train split, aggregated. Groups under ${int(parseFloat(F("min_cell")))} loans are hidden. <a href="#filters">Back to the filters and the list</a></p>`;
    distChart($("d-dist"), f);
    rateChart($("d-rate"), f, overall, { valueLabels: f.rate_bins.length <= 11 ? "all" : "ends" });
  };

  const choose = (name, scroll) => {
    selected = name;
    renderTable(); renderDetail();
    if (scroll) { const top = detail.getBoundingClientRect().top + window.scrollY - 70; window.scrollTo({ top, behavior: "smooth" }); }
  };

  $("ex-body").addEventListener("click", (e) => {
    const t = e.target.closest("[data-n]");
    if (t) choose(t.dataset.n, true);
  });
  Object.values(sel).forEach((el) => el.addEventListener(el.tagName === "INPUT" ? "input" : "change", renderTable));
  $("f-reset").addEventListener("click", () => { Object.values(sel).forEach((el) => { el.value = ""; }); selected = null; renderTable(); renderDetail(); });

  renderTable();
  renderDetail();
}
