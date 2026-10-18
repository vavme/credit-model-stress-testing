"""Build-time checks for the static site: numbers, dashes, links, and the full build."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "site" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.path.insert(0, str(ROOT / "site"))
    spec.loader.exec_module(mod)
    return mod


checks = _load("checks")


def _mini_dist(tmp_path, html):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "facts.json").write_text(json.dumps({"facts": {"n": {"text": "184,506", "bare": "184,506"}}}), encoding="utf-8")
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    return tmp_path


def test_number_check_accepts_fact_numbers_and_skips_nocheck(tmp_path):
    d = _mini_dist(tmp_path, '<p class="nocheck">Section 4 of 9</p><p>There are 184,506 loans. EXT_SOURCE_3 is strong.</p>')
    assert checks.check_numbers(d) == []


def test_number_check_rejects_hand_typed_numbers(tmp_path):
    d = _mini_dist(tmp_path, "<p>About 99 percent of loans.</p>")
    assert any("'99'" in p for p in checks.check_numbers(d))


def test_dash_check(tmp_path):
    d = _mini_dist(tmp_path, "<p>Nice \u2014 text</p>")
    assert checks.check_dashes(d)


def test_link_check(tmp_path):
    d = _mini_dist(tmp_path, '<a href="/base/missing.html">x</a><a href="#nope">y</a><a href="/other/index.html">z</a>')
    problems = checks.check_links(d, "/base/")
    assert len(problems) == 3


def test_full_build_passes_all_checks():
    build_site = _load("build_site")
    build_site.build()
    assert checks.check_data(ROOT / "site") == []
    assert checks.check_dist() == []


def test_base_path_can_be_overridden_for_root_hosting(monkeypatch):
    monkeypatch.setenv("SITE_BASE_PATH", "/")
    build_site = _load("build_site")
    build_site.build()
    assert 'data-base="/"' in (ROOT / "site" / "dist" / "index.html").read_text(encoding="utf-8")
    assert checks.check_dist() == []
    monkeypatch.delenv("SITE_BASE_PATH")
    build_site.build()
    assert 'data-base="/credit-model-stress-testing/"' in (ROOT / "site" / "dist" / "index.html").read_text(encoding="utf-8")


def test_pages_workflow_is_valid_yaml_with_the_expected_jobs():
    import yaml

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8"))
    assert set(wf["jobs"]) == {"build", "deploy"}
    assert wf["permissions"] == {"contents": "read", "pages": "write", "id-token": "write"}
    assert any("site/build_site.py" in str(s.get("run", "")) for s in wf["jobs"]["build"]["steps"])
