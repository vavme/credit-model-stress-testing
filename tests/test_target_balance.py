"""Unit tests for the Section 4 helpers (synthetic data only)."""

import numpy as np
import pandas as pd
import pytest

from src.data.target_balance import imbalance_stats, useless_score_metrics


def _y(n: int = 20_000, rate: float = 0.08) -> pd.Series:
    return pd.Series(np.random.default_rng(1).binomial(1, rate, n))


def test_imbalance_stats():
    y = pd.Series([0] * 9 + [1])
    s = imbalance_stats(y)
    assert s["ratio"] == 9
    assert s["acc_all_zero"] == 0.9


def test_useless_scores_sit_at_the_floor():
    y = _y()
    m = useless_score_metrics(y)
    assert m["auc_const"] == 0.5
    assert m["auc_rand"] == pytest.approx(0.5, abs=0.02)
    assert m["ap_const"] == pytest.approx(y.mean(), abs=1e-9)
    assert m["ks_rand"] < 0.05
