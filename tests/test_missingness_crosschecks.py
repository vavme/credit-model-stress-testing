"""Unit tests for the missingness cross-checks."""

import numpy as np
import pandas as pd

from src.data.missingness_crosschecks import build_crosschecks, missing_share_by_group


def _toy() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "FLAG_OWN_CAR": ["Y", "Y", "N", "N", "N"],
            "OWN_CAR_AGE": [3.0, np.nan, np.nan, np.nan, np.nan],
            "NAME_INCOME_TYPE": ["Working", "Working", "Pensioner", "Pensioner", "Working"],
            "OCCUPATION_TYPE": ["Laborers", np.nan, np.nan, np.nan, "Drivers"],
            "EXT_SOURCE_1": [0.1, np.nan, 0.3, np.nan, 0.5],
            "EXT_SOURCE_3": [np.nan, np.nan, 0.2, 0.4, 0.6],
            "TARGET": [0, 0, 1, 1, 0],
        }
    )


def test_missing_share_by_group():
    out = missing_share_by_group(_toy(), "OWN_CAR_AGE", "FLAG_OWN_CAR").set_index("FLAG_OWN_CAR")

    assert out.loc["Y", "rows"] == 2
    assert out.loc["Y", "missing_pct"] == 50.0
    assert out.loc["N", "rows"] == 3
    assert out.loc["N", "missing_pct"] == 100.0


def test_build_crosschecks_tables():
    df = _toy()
    before = df.copy()
    tables = build_crosschecks(df)
    pd.testing.assert_frame_equal(df, before)

    occ = list(tables.values())[1].set_index("NAME_INCOME_TYPE")
    assert occ.loc["Pensioner", "missing_pct"] == 100.0
    assert abs(occ.loc["Working", "missing_pct"] - 100 / 3) < 1e-9

    ext = list(tables.values())[2]
    row = ext[(ext["column"] == "EXT_SOURCE_1") & (ext["TARGET"] == 1)].iloc[0]
    assert row["rows"] == 2
    assert row["missing_pct"] == 50.0
