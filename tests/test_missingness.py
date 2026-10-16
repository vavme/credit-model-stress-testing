"""Unit tests for the missingness map (tracker 1.4)."""

import numpy as np
import pandas as pd

from src.data.missingness import column_family, missingness_table, summarize


def _toy() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "A": [1.0, np.nan, np.nan, np.nan],  # 75%
            "B": [1.0, 2.0, np.nan, np.nan],  # 50%
            "C": [1.0, 2.0, 3.0, np.nan],  # 25%
            "D": ["x", "y", "z", "w"],  # 0%
            "APARTMENTS_AVG": [np.nan, 1.0, 2.0, 3.0],  # 25%
        }
    )


def test_table_has_one_row_per_column_sorted_desc():
    table = missingness_table(_toy())

    assert len(table) == 5
    assert table["column"].iloc[0] == "A"
    assert table["missing_pct"].is_monotonic_decreasing
    row = table.set_index("column").loc["B"]
    assert row["missing_count"] == 2
    assert row["missing_pct"] == 50.0
    assert row["dtype"] == "float64"


def test_summary_thresholds_are_strictly_above():
    summary = summarize(missingness_table(_toy()), n_rows=4)

    assert summary["above_50"] == 1  # A only; B is exactly 50%
    assert summary["above_30"] == 2  # A, B
    assert summary["above_10"] == 4  # A, B, C, APARTMENTS_AVG
    assert summary["any_missing"] == 4


def test_family_grouping_is_name_based():
    assert column_family("APARTMENTS_AVG") == "building/housing attributes (_AVG/_MODE/_MEDI)"
    assert column_family("EXT_SOURCE_2") == "EXT_SOURCE_*"
    assert column_family("AMT_REQ_CREDIT_BUREAU_DAY") == "AMT_REQ_CREDIT_BUREAU_*"
    assert column_family("OWN_CAR_AGE") == "other (ungrouped)"


def test_table_is_pure():
    df = _toy()
    before = df.copy()
    missingness_table(df)
    pd.testing.assert_frame_equal(df, before)
