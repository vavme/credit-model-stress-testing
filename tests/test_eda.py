"""Unit tests for the descriptive EDA helpers (tracker 1.6)."""

import numpy as np
import pandas as pd
import pytest

from src.data.eda import (
    DAYS_EMPLOYED_SENTINEL,
    column_group,
    default_rate_by_category,
    group_counts,
    numeric_views,
)


def test_default_rate_by_category_counts_missing():
    df = pd.DataFrame(
        {"C": ["a", "a", "b", np.nan], "TARGET": [1, 0, 0, 1]}
    )
    out = default_rate_by_category(df, "C").set_index("C")

    assert out.loc["a", "rows"] == 2
    assert out.loc["a", "default_rate_pct"] == 50.0
    assert out.loc["b", "default_rate_pct"] == 0.0
    assert out.loc["missing", "default_rate_pct"] == 100.0


def test_numeric_views_drop_sentinel_and_convert_age():
    df = pd.DataFrame(
        {
            "AMT_INCOME_TOTAL": [100_000.0, 1_000.0],
            "AMT_CREDIT": [1.0, 2.0],
            "AMT_ANNUITY": [1.0, 2.0],
            "AMT_GOODS_PRICE": [1.0, 2.0],
            "DAYS_BIRTH": [-365.25 * 40, -365.25 * 30],
            "DAYS_EMPLOYED": [-365.25 * 5, DAYS_EMPLOYED_SENTINEL],
            "EXT_SOURCE_1": [0.1, 0.2],
            "EXT_SOURCE_2": [0.1, 0.2],
            "EXT_SOURCE_3": [0.1, 0.2],
        }
    )
    before = df.copy()
    views = numeric_views(df)

    pd.testing.assert_frame_equal(df, before)
    assert views["Age (years, from DAYS_BIRTH)"].tolist() == pytest.approx([40.0, 30.0])
    employed = views["Years employed (sentinel excluded)"]
    assert employed.iloc[0] == pytest.approx(5.0)
    assert np.isnan(employed.iloc[1])
    assert views["AMT_INCOME_TOTAL (log10)"].tolist() == pytest.approx([5.0, 3.0])


def test_column_groups_cover_known_names_and_reject_unknown():
    names = ["SK_ID_CURR", "TARGET", "AMT_CREDIT", "APARTMENTS_AVG", "EXT_SOURCE_1",
             "FLAG_DOCUMENT_3", "OBS_30_CNT_SOCIAL_CIRCLE", "AMT_REQ_CREDIT_BUREAU_DAY",
             "REG_CITY_NOT_LIVE_CITY", "FLAG_EMAIL", "DAYS_LAST_PHONE_CHANGE"]
    groups = group_counts(names)
    assert sum(len(v) for v in groups.values()) == len(names)
    assert column_group("APARTMENTS_AVG") == "Building / housing attributes"

    with pytest.raises(ValueError):
        group_counts(["SOME_NEW_COLUMN"])
