"""Unit tests for the Section 5 helpers (synthetic data only)."""

import numpy as np
import pandas as pd
import pytest

from src.data.missingness_baseline import adjusted_gap, cramers_v, default_rate_gap, mask_clusters


def test_mask_clusters_groups_identical_masks():
    df = pd.DataFrame({"a": [1, None, 3, 4], "b": [5, None, 7, 8], "c": [None, 2, 3, 4], "d": [1, 2, 3, 4]})
    assert mask_clusters(df) == [["a", "b"], ["c"]] or mask_clusters(df) == [["c"], ["a", "b"]]


def test_default_rate_gap_detects_informative_missingness():
    rng = np.random.default_rng(0)
    n = 40_000
    miss = rng.random(n) < 0.3
    y = np.where(miss, rng.random(n) < 0.12, rng.random(n) < 0.06).astype(int)
    out = default_rate_gap(y, miss)
    assert out["gap_pp"] == pytest.approx(6.0, abs=1.0)
    assert out["informative"]


def test_default_rate_gap_not_flagged_when_independent():
    rng = np.random.default_rng(1)
    n = 40_000
    out = default_rate_gap((rng.random(n) < 0.08).astype(int), rng.random(n) < 0.3)
    assert not out["informative"]


def test_adjusted_gap_removes_confounding():
    rng = np.random.default_rng(2)
    n = 80_000
    s = pd.Series(rng.choice(["a", "b"], n))
    miss = np.where(s == "a", rng.random(n) < 0.8, rng.random(n) < 0.2)
    y = np.where(s == "a", rng.random(n) < 0.15, rng.random(n) < 0.05).astype(int)  # TARGET depends on stratum only
    raw = default_rate_gap(y, miss)["gap_pp"]
    adj, used = adjusted_gap(y, miss, s)
    assert raw > 4
    assert abs(adj) < 1
    assert used == 1.0


def test_cramers_v_perfect_and_none():
    a = pd.Series([0, 1] * 500)
    assert cramers_v(a, a.astype(str)) == pytest.approx(1.0)
    rng = np.random.default_rng(3)
    assert cramers_v(pd.Series(rng.integers(0, 2, 5000)), pd.Series(rng.integers(0, 3, 5000))) < 0.05
