"""Unit tests for the Section 3 catalog helpers (synthetic data only)."""

import numpy as np
import pandas as pd

from src.data.feature_catalog import build_catalog, column_notes, semantic_type, top_share


def _df(n: int = 1_000) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "SK_ID_CURR": np.arange(n),
            "TARGET": rng.binomial(1, 0.1, n),
            "FLAG_OWN_CAR": rng.choice(["Y", "N"], n),
            "CODE_GENDER": rng.choice(["F", "M", "XNA"], n),
            "CNT_CHILDREN": rng.integers(0, 4, n),
            "AMT_INCOME_TOTAL": rng.normal(150_000, 30_000, n),
            "DAYS_EMPLOYED": np.where(rng.random(n) < 0.2, 365243, -rng.integers(1, 5000, n)),
        }
    )


def test_semantic_types():
    df = _df()
    assert semantic_type("SK_ID_CURR", df["SK_ID_CURR"]) == "ID"
    assert semantic_type("TARGET", df["TARGET"]) == "target"
    assert semantic_type("FLAG_OWN_CAR", df["FLAG_OWN_CAR"]) == "binary flag"
    assert semantic_type("CODE_GENDER", df["CODE_GENDER"]) == "nominal"
    assert semantic_type("CNT_CHILDREN", df["CNT_CHILDREN"]) == "numeric count"
    assert semantic_type("AMT_INCOME_TOTAL", df["AMT_INCOME_TOTAL"]) == "numeric continuous"


def test_notes_flag_placeholder_and_xna():
    df = _df()
    assert "placeholder 365243" in column_notes("DAYS_EMPLOYED", df["DAYS_EMPLOYED"], len(df))
    assert "XNA" in column_notes("CODE_GENDER", df["CODE_GENDER"], len(df))


def test_catalog_has_one_row_per_column():
    df = _df()
    cat = build_catalog(df, {})
    assert cat["name"].tolist() == df.columns.tolist()
    assert top_share(pd.Series([1, 1, 1, 2])) == 0.75
