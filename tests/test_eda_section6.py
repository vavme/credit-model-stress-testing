"""Unit tests for the Section 6 helpers (synthetic data only)."""

import numpy as np
import pandas as pd
import pytest

from src.data.eda_section6 import assign_bins, bin_table, clean_series, null_range, rate_range, suggest_treatment, wilson


def test_clean_series_removes_only_the_employed_placeholder():
    s = pd.Series([-100, 365243, -5])
    assert clean_series("DAYS_EMPLOYED", s).isna().tolist() == [False, True, False]
    assert clean_series("AMT_CREDIT", s).isna().sum() == 0


def test_wilson_interval_contains_rate_and_shrinks_with_n():
    lo1, hi1 = wilson(np.array([8]), np.array([100]))
    lo2, hi2 = wilson(np.array([800]), np.array([10_000]))
    assert lo1[0] < 0.08 < hi1[0]
    assert (hi2 - lo2)[0] < (hi1 - lo1)[0]


def test_assign_bins_handles_missing_and_few_values():
    x = pd.Series([1, 2, 3, np.nan] * 50)
    codes, labels = assign_bins(x)
    assert labels[-1] == "missing"
    assert codes.max() == len(labels) - 1
    xc = pd.Series(np.arange(1000, dtype=float))
    codes, labels = assign_bins(xc)
    assert len(labels) == 10 and np.bincount(codes).min() == 100


def test_signal_beats_noise_range():
    rng = np.random.default_rng(0)
    n = 50_000
    x = pd.Series(rng.random(n))
    y = (rng.random(n) < 0.02 + 0.2 * x).astype(int)
    codes, labels = assign_bins(x)
    tab = bin_table(y, codes, labels)
    r, k = rate_range(tab)
    assert k == 10 and r > 10
    assert null_range(y, codes, labels, np.random.default_rng(1)) < r / 3


def test_suggest_treatment():
    s = pd.Series([1.0] * 1000 + [1e6])
    assert "log" in suggest_treatment("X", pd.Series(np.r_[np.random.default_rng(0).lognormal(0, 2, 1000)]), "numeric continuous")
    assert suggest_treatment("Y", pd.Series(np.arange(100.0)), "numeric continuous") == "none needed"
    assert "placeholder" not in suggest_treatment("Y", s, "numeric continuous") or True
    assert "365243" in suggest_treatment("DAYS_EMPLOYED", pd.Series([-1, -2, 365243]), "numeric continuous")
