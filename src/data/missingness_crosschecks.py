"""Missingness cross-checks for the training split (follow-up to tracker 1.4).

Reads data/processed/train.csv ONLY (val/test are never opened). Reports
numbers only; no interpretation. Writes docs/eda/missingness_crosschecks.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
OUT_PATH = ROOT / "docs" / "eda" / "missingness_crosschecks.md"

COLUMNS = [
    "FLAG_OWN_CAR",
    "OWN_CAR_AGE",
    "OCCUPATION_TYPE",
    "NAME_INCOME_TYPE",
    "EXT_SOURCE_1",
    "EXT_SOURCE_3",
    "TARGET",
]


def missing_share_by_group(df: pd.DataFrame, target_col: str, group_col: str) -> pd.DataFrame:
    """Rows, missing count and missing % of target_col within each group_col value. Pure."""
    grouped = df.groupby(group_col, dropna=False)[target_col]
    out = pd.DataFrame(
        {
            "rows": grouped.size(),
            "missing_count": grouped.apply(lambda s: int(s.isna().sum())),
        }
    )
    out["missing_pct"] = out["missing_count"] / out["rows"] * 100.0
    return out.reset_index().rename(columns={group_col: group_col})


def build_crosschecks(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The three cross-check tables. Pure."""
    car = missing_share_by_group(df, "OWN_CAR_AGE", "FLAG_OWN_CAR")
    occupation = missing_share_by_group(
        df, "OCCUPATION_TYPE", "NAME_INCOME_TYPE"
    ).sort_values("missing_pct", ascending=False, kind="stable")
    ext = {
        col: missing_share_by_group(df, col, "TARGET").assign(column=col)
        for col in ("EXT_SOURCE_1", "EXT_SOURCE_3")
    }
    ext_by_target = pd.concat(ext.values(), ignore_index=True)[
        ["column", "TARGET", "rows", "missing_count", "missing_pct"]
    ]
    return {
        "OWN_CAR_AGE missing, by FLAG_OWN_CAR": car,
        "OCCUPATION_TYPE missing, by NAME_INCOME_TYPE": occupation.reset_index(drop=True),
        "EXT_SOURCE_1 / EXT_SOURCE_3 missing, by TARGET (0 = repaid, 1 = default)": ext_by_target,
    }


def _to_markdown(table: pd.DataFrame) -> str:
    cols = list(table.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in table.itertuples(index=False):
        cells = [
            f"{v:,.2f}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v)
            for v in row
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_markdown(tables: dict[str, pd.DataFrame], n_rows: int) -> str:
    parts = [
        "# Missingness cross-checks (train split only)",
        "",
        f"Rows: {n_rows:,}. Computed from `data/processed/train.csv` by "
        "`src/data/missingness_crosschecks.py`. Numbers only; no interpretation.",
        "",
    ]
    for title, table in tables.items():
        parts += [f"## {title}", "", _to_markdown(table), ""]
    return "\n".join(parts)


def run() -> None:
    df = pd.read_csv(TRAIN_PATH, usecols=COLUMNS)
    tables = build_crosschecks(df)
    text = render_markdown(tables, len(df))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(text)
    print(f"Written to {OUT_PATH}")


if __name__ == "__main__":
    run()
