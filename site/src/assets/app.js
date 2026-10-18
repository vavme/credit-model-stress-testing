// Entry point for every page. Loads the data, then starts the page's module.
import { loadData, fact } from "./data.js";

const page = document.body.dataset.page;

// Scrollable areas must be reachable with the keyboard and have a name.
function makeScrollAreasFocusable() {
  const seen = {};
  document.querySelectorAll(".scrollx").forEach((el) => {
    if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "0");
    if (!el.hasAttribute("role")) el.setAttribute("role", "region");
    if (!el.hasAttribute("aria-label")) {
      const fig = el.closest("figure");
      const cap = el.querySelector("caption") || (fig && fig.querySelector("figcaption"));
      const base = cap ? cap.textContent.trim().slice(0, 80) : "Scrollable content";
      seen[base] = (seen[base] || 0) + 1;
      el.setAttribute("aria-label", seen[base] > 1 ? `${base} (part ${seen[base]})` : base);
    }
  });
}

async function start() {
  makeScrollAreasFocusable();
  const d = await loadData();
  const F = (k) => fact(d, k);
  if (page === "index") {
    const { initStory } = await import("./story.js");
    initStory(d, F);
  } else if (page === "explorer") {
    const { initExplorer } = await import("./explorer.js");
    initExplorer(d, F);
  }
  // highlight the current page in the navigation
  document.querySelectorAll(".navlinks a[data-page]").forEach((a) => {
    if (a.dataset.page === page) a.setAttribute("aria-current", "true");
  });
}

start().catch((err) => {
  console.error(err);
  const m = document.getElementById("main");
  if (m) m.insertAdjacentHTML("afterbegin", '<p class="wrap" role="alert">The charts could not be loaded. The text on this page is still complete.</p>');
});
