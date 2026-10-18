// Loads the aggregated JSON the build wrote. Everything shown comes from these files.
export const BASE = document.documentElement.dataset.base || "/";

let cache = null;

async function get(name) {
  const r = await fetch(BASE + "data/" + name);
  if (!r.ok) throw new Error("Could not load " + name);
  return r.json();
}

export async function loadData() {
  if (cache) return cache;
  const [facts, charts, features, site, content] = await Promise.all([
    get("facts.json"), get("charts.json"), get("features.json"), get("site.json"), get("content.json"),
  ]);
  cache = { facts: facts.facts, charts, features, site, content };
  return cache;
}

export const fact = (d, key) => {
  const f = d.facts[key];
  if (!f) throw new Error("Unknown fact " + key);
  return f.text;
};

export const int = (n) => Math.round(n).toLocaleString("en-US");
export const pct = (n, digits = 2) => n.toFixed(digits) + "%";
export const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
