"""Unit tests for the Phase 1 integrity helpers (synthetic data only)."""

import numpy as np
import pandas as pd

from src.data.integrity import check_raw, constant_columns, split_indices


def _fake(n: int = 5_000) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "SK_ID_CURR": np.arange(100, 100 + n),
            "TARGET": rng.binomial(1, 0.08, size=n),
            "X": rng.normal(size=n),
            "CONST": 1,
        }
    )


def test_check_raw_flags_duplicates_and_bad_target():
    df = _fake()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    df.loc[1, "TARGET"] = np.nan
    out = check_raw(df)
    assert out["duplicate_rows"] == 1
    assert out["duplicate_ids"] == 1
    assert out["target_missing"] == 1


def test_split_indices_cover_every_row_once_and_are_reproducible():
    df = _fake()
    a = split_indices(df)
    b = split_indices(df)
    assert a.equals(b)
    assert len(a) == len(df)
    assert a["raw_row"].is_unique
    assert set(a["split"]) == {"train", "val", "test"}


def test_constant_columns():
    assert constant_columns(_fake()) == ["CONST"]
