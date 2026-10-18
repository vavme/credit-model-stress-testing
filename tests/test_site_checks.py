"""The site data checks must pass on clean data and fail on row-level or ID-like data."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("site_checks", ROOT / "site" / "checks.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def _write(tmp_path, name, obj):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / name).write_text(json.dumps(obj), encoding="utf-8")


def test_clean_aggregates_pass(tmp_path):
    _write(tmp_path, "ok.json", {"bins": [{"label": "a", "n": 12, "rate": 8.1}], "facts": {"x": {"text": "8.07%"}}})
    assert checks.check_data(tmp_path) == []


def test_forbidden_keys_fail(tmp_path):
    for key in ("example_values", "sample", "SK_ID_CURR", "id", "row_index", "applicant_ids"):
        _write(tmp_path, "bad.json", {"rows": [{key: 1}]})
        assert any("forbidden key" in p for p in checks.check_data(tmp_path)), key


def test_id_like_array_and_long_array_fail(tmp_path):
    _write(tmp_path, "bad.json", {"v": list(range(100002, 100102))})
    assert any("SK_ID_CURR range" in p for p in checks.check_data(tmp_path))
    _write(tmp_path, "bad.json", {"v": [0.5] * 2500})
    assert any("array of" in p for p in checks.check_data(tmp_path))


def test_csv_files_and_headers_fail(tmp_path):
    (tmp_path / "t.csv").write_text("sample_value,n\n1,2\n", encoding="utf-8")
    problems = checks.check_data(tmp_path)
    assert any("raw-data file type" in p for p in problems)
    assert any("forbidden column" in p for p in problems)


def test_real_site_data_passes():
    assert checks.check_data(ROOT / "site") == []
