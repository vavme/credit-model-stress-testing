"""Site build, stage 2: render the pages into site/dist/ and run the checks.

    python site/build_site.py            # build, then run all checks (exit code 1 on failure)
    python site/build_site.py --no-checks

Standard library only. Reads site/config.json, site/data/*.json (made by build_data.py, committed),
site/src/ (templates and assets) and site/content/. Needs no raw data, so CI can run it.

Template tokens:
  {{base}}  {{config:key}}  {{f:fact_key}}  {{partial:name}}  {{tag:data|doc|general|nv|hyp}}
  {{term:slug|link text}}  {{draft}}  {{hypothesis}}  {{hypothesis_date}}  {{desc_source}}
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
SRC = SITE / "src"
DATA = SITE / "data"
DIST = SITE / "dist"
CONTENT = SITE / "content"

TAGS = {
    "data": ("Data", "Checked by code on the train split"),
    "doc": ("Doc", "Taken from the documentation (Kaggle column description or the project README)"),
    "general": ("General", "General domain knowledge, not checked here"),
    "nv": ("Not verified", "Could not be verified here"),
    "hyp": ("Hypothesis", "A reading or a prediction, not a finding"),
}
TOKEN = re.compile(r"\{\{([a-z_]+)(?::([^}|]*))?(?:\|([^}]*))?\}\}")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Renderer:
    def __init__(self) -> None:
        self.config = load_json(SITE / "config.json")
        self.facts = load_json(DATA / "facts.json")["facts"]
        self.content = load_json(DATA / "content.json")
        # SITE_BASE_PATH overrides the config, for hosts that serve from the root (for example Cloudflare Pages).
        self.base = os.environ.get("SITE_BASE_PATH") or self.config["base_path"]
        assert self.base.startswith("/") and self.base.endswith("/"), "base_path must start and end with /"

    def draft(self) -> str:
        if self.config["ai_draft_adopted"]:
            return f'<span class="authorlabel">{html.escape(self.config["ai_adopted_label"])}</span>'
        return f'<span class="draftlabel">{html.escape(self.config["ai_draft_label"])}</span>'

    def desc_source(self) -> str:
        return "the Kaggle column description file" if self.config["description_source"] == "kaggle" else "the author"

    def hypothesis(self) -> str:
        paras = [p.strip() for p in self.content["hypothesis"]["text"].split("\n\n") if p.strip()]
        return "".join(f"<p>{html.escape(p)}</p>" for p in paras)

    def sub(self, m: re.Match) -> str:
        kind, arg, extra = m.group(1), m.group(2), m.group(3)
        if kind == "base":
            return self.base
        if kind == "config":
            return html.escape(str(self.config[arg]))
        if kind == "f":
            if arg not in self.facts:
                raise KeyError(f"unknown fact: {arg}")
            return html.escape(self.facts[arg]["text"])
        if kind == "partial":
            return self.render((SRC / "partials" / f"{arg}.html").read_text(encoding="utf-8"))
        if kind == "tag":
            label, tip = TAGS[arg]
            return f'<span class="tag tag-{arg}" title="{html.escape(tip)}">{label}</span>'
        if kind == "term":
            return f'<a class="term" href="{self.base}glossary.html#{arg}">{html.escape(extra or arg)}</a>'
        if kind == "draft":
            return self.draft()
        if kind == "hypothesis":
            return self.hypothesis()
        if kind == "hypothesis_date":
            return html.escape(self.content["hypothesis"]["decided"])
        if kind == "inline_css":
            return "<style>" + (SRC / "assets" / "style.css").read_text(encoding="utf-8") + "</style>"
        if kind == "desc_source":
            return self.desc_source()
        raise KeyError(f"unknown token: {m.group(0)}")

    def render(self, text: str) -> str:
        prev = None
        while prev != text:  # partials can contain tokens
            prev = text
            text = TOKEN.sub(self.sub, text)
        return text


def write_features(cfg: dict) -> None:
    feats = load_json(DATA / "features.json")
    own_path = CONTENT / "own_descriptions.json"
    if cfg["description_source"] == "own":
        if not own_path.exists():
            own_path.write_text(json.dumps([{"name": f["name"], "description": ""} for f in feats], indent=2), encoding="utf-8")
        own = {row["name"]: row["description"] for row in load_json(own_path)}
        for f in feats:
            f["description"] = own.get(f["name"], "")
            f["description_source"] = "own"
    else:
        for f in feats:
            f["description_source"] = "kaggle"
    (DIST / "data" / "features.json").write_text(json.dumps(feats, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build() -> None:
    r = Renderer()
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "data").mkdir(parents=True)
    (DIST / "assets").mkdir()
    for page in sorted(SRC.glob("*.html")):
        (DIST / page.name).write_text(r.render(page.read_text(encoding="utf-8")), encoding="utf-8")
    for asset in sorted((SRC / "assets").iterdir()):
        shutil.copy(asset, DIST / "assets" / asset.name)
    for name in ("facts.json", "charts.json", "content.json"):
        shutil.copy(DATA / name, DIST / "data" / name)
    write_features(r.config)
    site_json = {k: r.config[k] for k in ("ai_draft_adopted", "ai_draft_label", "ai_adopted_label", "author_label", "description_source")}
    site_json["desc_label"] = "Source: Kaggle column description file" if r.config["description_source"] == "kaggle" else "Source: written by the author"
    (DIST / "data" / "site.json").write_text(json.dumps(site_json), encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    size = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"built {len(list(DIST.glob('*.html')))} pages into {DIST} ({size / 1024:.0f} KB), base path {r.base}")


def main() -> int:
    build()
    if "--no-checks" in sys.argv:
        return 0
    sys.path.insert(0, str(SITE))
    import checks  # noqa: PLC0415

    return checks.main(["--dist"])


if __name__ == "__main__":
    sys.exit(main())
