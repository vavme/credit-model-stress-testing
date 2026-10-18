"""Automated checks for the static site. Exit code 1 if any check fails.

    python site/checks.py            # data checks on site/ (JSON and CSV files)
    python site/checks.py --dist     # data checks plus checks on the built site/dist

Data checks:
  1. No raw-data file types in the site folder (csv, parquet, pickle, excel, sqlite).
  2. No column or key named like an example, a sample or an ID in any JSON or CSV file.
  3. No JSON array that looks like row-level data: more than MAX_ARRAY items, or 50+ integers
     that all fall in the SK_ID_CURR range.
  4. Size limits: whole site under 15 MB, data folder under 5 MB.
Built-site checks (--dist):
  5. No em dash or en dash anywhere in the built files.
  6. Every number in the page text is a number from facts.json (elements with class "nocheck" are skipped,
     they hold only section numbers and dates).
  7. Every internal link, script and stylesheet resolves under the base path, and every #anchor exists.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parent
DIST = SITE / "dist"
FORBIDDEN_SUFFIXES = {".csv", ".tsv", ".parquet", ".pkl", ".pickle", ".xlsx", ".xls", ".sqlite", ".db", ".feather"}
FORBIDDEN_KEY = re.compile(r"(example|sample|(^|[^a-z])ids?([^a-z]|$)|^sk_|row_?index|^index$)", re.I)
MAX_ARRAY = 2000
ID_RANGE = (100002, 456255)
SITE_LIMIT = 15 * 1024 * 1024
DATA_LIMIT = 5 * 1024 * 1024
DASHES = ("—", "–", "&mdash;", "&ndash;", "&#8212;", "&#8211;")
NUMBER = re.compile(r"(?<![A-Za-z_\d])\d[\d,]*(?:\.\d+)?")
TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".md", ".txt"}


def walk(obj, path="$"):
    """Yield (path, key, value) for every dict key and list in a JSON document."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path, k, v
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        yield path, None, obj
        for i, v in enumerate(obj[:50]):  # structure repeats, so a sample of items is enough
            yield from walk(v, f"{path}[{i}]")


def check_json(path: Path) -> list[str]:
    problems = []
    doc = json.loads(path.read_text(encoding="utf-8"))
    for where, key, value in walk(doc):
        if key is not None and FORBIDDEN_KEY.search(str(key)):
            problems.append(f"{path.name}: forbidden key '{key}' at {where}")
        if isinstance(value, list):
            if len(value) > MAX_ARRAY:
                problems.append(f"{path.name}: array of {len(value)} items at {where}")
            ints = [v for v in value if isinstance(v, int) and not isinstance(v, bool)]
            if len(ints) >= 50 and all(ID_RANGE[0] <= v <= ID_RANGE[1] for v in ints):
                problems.append(f"{path.name}: {len(ints)} integers in the SK_ID_CURR range at {where}")
    return problems


def check_csv(path: Path) -> list[str]:
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    return [f"{path.name}: forbidden column '{h}'" for h in header if FORBIDDEN_KEY.search(h)]


def check_data(site_dir: Path = SITE) -> list[str]:
    problems: list[str] = []
    total = data_total = 0
    for p in site_dir.rglob("*"):
        if not p.is_file() or "__pycache__" in p.parts or p.name.endswith(".pyc"):
            continue
        total += p.stat().st_size
        if "data" in p.relative_to(site_dir).parts[:1]:
            data_total += p.stat().st_size
        if p.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"{p.relative_to(site_dir)}: raw-data file type {p.suffix}")
            if p.suffix.lower() == ".csv":
                problems += check_csv(p)
        elif p.suffix.lower() == ".json":
            problems += check_json(p)
    if total > SITE_LIMIT:
        problems.append(f"site is {total / 1e6:.1f} MB, limit {SITE_LIMIT / 1e6:.0f} MB")
    if data_total > DATA_LIMIT:
        problems.append(f"data folder is {data_total / 1e6:.1f} MB, limit {DATA_LIMIT / 1e6:.0f} MB")
    return problems


# ---------------------------------------------------------------- built-site checks
class PageParser(HTMLParser):
    """Collects visible text (skipping script, style and .nocheck), ids and links."""

    VOID = {"meta", "link", "br", "hr", "img", "input", "source", "area", "base", "col", "embed", "param", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.ids: set[str] = set()
        self.links: list[tuple[str, str]] = []
        self.stack: list[tuple[str, bool]] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key) is not None and tag in ("a", "link", "script", "img"):
                self.links.append((tag, a[key]))
        if tag in self.VOID:
            return
        skip_here = tag in ("script", "style") or "nocheck" in (a.get("class") or "").split()
        self.stack.append((tag, skip_here))
        if skip_here:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        while self.stack:
            t, skipped = self.stack.pop()
            if skipped:
                self.skip -= 1
            if t == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def norm_number(tok: str) -> str:
    return tok.strip("+-").rstrip("%").rstrip(".,")


def allowed_numbers(dist: Path) -> set[str]:
    facts = json.loads((dist / "data" / "facts.json").read_text(encoding="utf-8"))["facts"]
    allowed: set[str] = set()
    for f in facts.values():
        for key in ("text", "bare"):
            allowed |= {norm_number(m) for m in NUMBER.findall(str(f[key]))}
    return allowed


def check_dashes(dist: Path) -> list[str]:
    problems = []
    for p in dist.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
            text = p.read_text(encoding="utf-8")
            for d in DASHES:
                if d in text:
                    problems.append(f"{p.relative_to(dist)}: contains a dash character {d!r} ({text.count(d)} times)")
    return problems


def check_numbers(dist: Path) -> list[str]:
    allowed = allowed_numbers(dist)
    problems = []
    for page in sorted(dist.glob("*.html")):
        parser = PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        text = " ".join(parser.text)
        for m in NUMBER.finditer(text):
            tok = norm_number(m.group(0))
            if tok not in allowed:
                ctx = text[max(0, m.start() - 40): m.end() + 30].replace("\n", " ")
                problems.append(f"{page.name}: number '{tok}' is not in facts.json (...{ctx}...)")
    return problems


def check_links(dist: Path, base: str) -> list[str]:
    problems = []
    parsed: dict[str, PageParser] = {}
    for page in dist.glob("*.html"):
        pp = PageParser()
        pp.feed(page.read_text(encoding="utf-8"))
        parsed[page.name] = pp
    for name, pp in parsed.items():
        for tag, href in pp.links:
            if re.match(r"^(https?:|mailto:|tel:|data:)", href):
                continue
            if href.startswith("#"):
                if href[1:] and href[1:] not in pp.ids:
                    problems.append(f"{name}: anchor {href} does not exist on the page")
                continue
            if not href.startswith(base):
                problems.append(f"{name}: link '{href}' is not under the base path {base}")
                continue
            rel, _, frag = href[len(base):].partition("#")
            rel = rel.split("?")[0] or "index.html"
            target = dist / rel
            if not target.is_file():
                problems.append(f"{name}: link '{href}' points to a missing file")
            elif frag and rel.endswith(".html") and frag not in parsed[rel].ids:
                problems.append(f"{name}: link '{href}' points to a missing anchor")
    return problems


def check_dist(dist: Path = DIST) -> list[str]:
    base = os.environ.get("SITE_BASE_PATH") or json.loads((SITE / "config.json").read_text(encoding="utf-8"))["base_path"]
    return check_dashes(dist) + check_numbers(dist) + check_links(dist, base)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    problems = check_data()
    if "--dist" in argv:
        problems += check_dist()
    if problems:
        print(f"CHECKS FAILED ({len(problems)})")
        for p in problems[:80]:
            print(" -", p)
        return 1
    print("all checks passed" if "--dist" in argv else "data checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
