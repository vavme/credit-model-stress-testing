"""Unit tests for the 60/20/20 split (tracker 1.2/1.3, per 0.4/0.10)."""

import numpy as np
import pandas as pd
import pytest

from src.data.split import SEED, make_split


def _fake_applications(n: int = 10_000, default_rate: float = 0.08) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "SK_ID_CURR": np.arange(n),
            "TARGET": rng.binomial(1, default_rate, size=n),
            "AMT_INCOME_TOTAL": rng.normal(150_000, 50_000, size=n),
        }
    )


def test_split_sizes_are_60_20_20():
    df = _fake_applications()
    train_df, val_df, test_df = make_split(df)

    assert len(train_df) + len(val_df) + len(test_df) == len(df)
    assert len(train_df) / len(df) == pytest.approx(0.6, abs=0.01)
    assert len(val_df) / len(df) == pytest.approx(0.2, abs=0.01)
    assert len(test_df) / len(df) == pytest.approx(0.2, abs=0.01)


def test_split_is_disjoint_and_covers_all_rows():
    df = _fake_applications()
    train_df, val_df, test_df = make_split(df)

    train_ids = set(train_df["SK_ID_CURR"])
    val_ids = set(val_df["SK_ID_CURR"])
    test_ids = set(test_df["SK_ID_CURR"])

    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)
    assert train_ids | val_ids | test_ids == set(df["SK_ID_CURR"])


def test_split_preserves_default_rate_stratification():
    df = _fake_applications()
    overall_rate = df["TARGET"].mean()
    train_df, val_df, test_df = make_split(df)

    for split_df in (train_df, val_df, test_df):
        assert abs(split_df["TARGET"].mean() - overall_rate) < 0.01


def test_split_is_reproducible_with_fixed_seed():
    df = _fake_applications()
    train_a, val_a, test_a = make_split(df, seed=SEED)
    train_b, val_b, test_b = make_split(df, seed=SEED)

    pd.testing.assert_frame_equal(train_a, train_b)
    pd.testing.assert_frame_equal(val_a, val_b)
    pd.testing.assert_frame_equal(test_a, test_b)
