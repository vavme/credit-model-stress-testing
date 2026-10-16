"""Missingness map for the training split (tracker 1.4).

Reads data/processed/train.csv ONLY — val.csv and test.csv are never opened
here (CLAUDE.md, split rule). Writes a per-column table, a bar chart, and a
short numeric summary to docs/eda/. Reports numbers only; deciding which
columns matter is the feature shortlist (1.5) and is not done here.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
EDA_DIR = ROOT / "docs" / "eda"

THRESHOLDS = (0.50, 0.30, 0.10)

# Name-based families only (no judgement about relevance). First match wins.
FAMILY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("building/housing attributes (_AVG/_MODE/_MEDI)", re.compile(r".*_(AVG|MODE|MEDI)$")),
    ("EXT_SOURCE_*", re.compile(r"^EXT_SOURCE_\d+$")),
    ("AMT_REQ_CREDIT_BUREAU_*", re.compile(r"^AMT_REQ_CREDIT_BUREAU_")),
    ("*_SOCIAL_CIRCLE", re.compile(r".*_SOCIAL_CIRCLE$")),
    ("FLAG_DOCUMENT_*", re.compile(r"^FLAG_DOCUMENT_\d+$")),
]
OTHER_FAMILY = "other (ungrouped)"


def column_family(name: str) -> str:
    for family, pattern in FAMILY_PATTERNS:
        if pattern.match(name):
            return family
    return OTHER_FAMILY


def missingness_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per column: dtype, missing count, missing %, family. Pure."""
    n = len(df)
    missing = df.isna().sum()
    table = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(t) for t in df.dtypes],
            "missing_count": missing.to_numpy(),
            "missing_pct": (missing.to_numpy() / n * 100.0) if n else 0.0,
            "family": [column_family(c) for c in df.columns],
        }
    )
    return table.sort_values(
        ["missing_pct", "column"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)


def summarize(table: pd.DataFrame, n_rows: int) -> dict:
    """Counts above each threshold and per-family breakdown. Pure."""
    summary: dict = {"n_rows": n_rows, "n_columns": len(table)}
    summary["any_missing"] = int((table["missing_count"] > 0).sum())
    for t in THRESHOLDS:
        summary[f"above_{int(t * 100)}"] = int((table["missing_pct"] > t * 100).sum())

    families = {}
    for family, grp in table.groupby("family"):
        families[family] = {
            "columns": len(grp),
            "any_missing": int((grp["missing_count"] > 0).sum()),
            **{
                f"above_{int(t * 100)}": int((grp["missing_pct"] > t * 100).sum())
                for t in THRESHOLDS
            },
        }
    summary["families"] = families
    return summary


def plot_missingness(table: pd.DataFrame, path: Path) -> None:
    """Horizontal bar chart of missing % for columns with any missing."""
    shown = table[table["missing_count"] > 0].iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, max(4, 0.17 * len(shown) + 1)))
    ax.barh(shown["column"], shown["missing_pct"], color="#4c72b0")
    for pct in (10, 30, 50):
        ax.axvline(pct, color="grey", linestyle="--", linewidth=0.7)
    ax.set_xlabel("Missing (%) in train split")
    ax.set_title(f"Missingness by column ({len(shown)} of {len(table)} columns have any missing)")
    ax.tick_params(axis="y", labelsize=6)
    ax.set_xlim(0, 100)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def summary_markdown(summary: dict, table: pd.DataFrame) -> str:
    lines = [
        "# Missingness summary (train split only)",
        "",
        f"Rows: {summary['n_rows']:,}. Columns: {summary['n_columns']}.",
        "Computed from `data/processed/train.csv` by `src/data/missingness.py`. "
        "Numbers only; no judgement about which columns matter (that is 1.5).",
        "",
        "## Columns by missingness",
        "",
        "| Threshold | Columns |",
        "|---|---|",
        f"| > 50% missing | {summary['above_50']} |",
        f"| > 30% missing | {summary['above_30']} |",
        f"| > 10% missing | {summary['above_10']} |",
        f"| any missing | {summary['any_missing']} |",
        "",
        "## By column family (grouped by column name only)",
        "",
        "| Family | Columns | Any missing | > 10% | > 30% | > 50% |",
        "|---|---|---|---|---|---|",
    ]
    for family, f in sorted(
        summary["families"].items(), key=lambda kv: (-kv[1]["any_missing"], kv[0])
    ):
        lines.append(
            f"| {family} | {f['columns']} | {f['any_missing']} | "
            f"{f['above_10']} | {f['above_30']} | {f['above_50']} |"
        )

    other = table[(table["family"] == OTHER_FAMILY) & (table["missing_count"] > 0)]
    lines += ["", "## Ungrouped columns with any missing", ""]
    if other.empty:
        lines.append("None.")
    else:
        lines += ["| Column | Missing % |", "|---|---|"]
        lines += [f"| {r.column} | {r.missing_pct:.2f} |" for r in other.itertuples()]
    lines.append("")
    return "\n".join(lines)


def run() -> None:
    df = pd.read_csv(TRAIN_PATH)
    table = missingness_table(df)
    summary = summarize(table, len(df))

    EDA_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(EDA_DIR / "missingness_table.csv", index=False, float_format="%.4f")
    plot_missingness(table, EDA_DIR / "missingness_bar.png")
    (EDA_DIR / "missingness_summary.md").write_text(
        summary_markdown(summary, table), encoding="utf-8"
    )

    print(f"Source: {TRAIN_PATH} ({len(df):,} rows, {len(table)} columns)")
    print(
        f"> 50%: {summary['above_50']}  > 30%: {summary['above_30']}  "
        f"> 10%: {summary['above_10']}  any: {summary['any_missing']}"
    )
    print(f"Written to {EDA_DIR}")


if __name__ == "__main__":
    run()
