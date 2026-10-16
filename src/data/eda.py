"""Descriptive EDA charts and dataset overview for the training split (tracker 1.6).

Reads data/processed/train.csv ONLY (val/test are never opened). Writes PNG
charts and docs/eda/dataset_overview.md. Descriptive only: the columns plotted
are the core application fields shown for orientation, not a feature shortlist
(that is 1.5 and stays with Vav).
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
EDA_DIR = ROOT / "docs" / "eda"

DAYS_EMPLOYED_SENTINEL = 365243
COLORS = {0: "#4c72b0", 1: "#c44e52"}

CATEGORY_PANELS = [
    "NAME_CONTRACT_TYPE",
    "CODE_GENDER",
    "FLAG_OWN_CAR",
    "FLAG_OWN_REALTY",
    "NAME_INCOME_TYPE",
    "NAME_EDUCATION_TYPE",
    "NAME_FAMILY_STATUS",
    "NAME_HOUSING_TYPE",
]

# (title, description, matcher). First match wins; every column must match one.
GROUPS: list[tuple[str, str, re.Pattern[str]]] = [
    ("ID and label", "Applicant id and the default flag (TARGET: 1 = payment difficulty / default).",
     re.compile(r"^(SK_ID_CURR|TARGET)$")),
    ("Loan terms", "Contract type and the credit, annuity and goods price of the loan applied for.",
     re.compile(r"^(NAME_CONTRACT_TYPE|AMT_CREDIT|AMT_ANNUITY|AMT_GOODS_PRICE)$")),
    ("Client demographics", "Gender, children, family, education, housing and who accompanied the applicant.",
     re.compile(r"^(CODE_GENDER|CNT_CHILDREN|CNT_FAM_MEMBERS|NAME_TYPE_SUITE|NAME_FAMILY_STATUS|"
                r"NAME_EDUCATION_TYPE|NAME_HOUSING_TYPE|DAYS_BIRTH)$")),
    ("Income and employment", "Income amount and type, occupation, employer type, time employed.",
     re.compile(r"^(AMT_INCOME_TOTAL|NAME_INCOME_TYPE|OCCUPATION_TYPE|ORGANIZATION_TYPE|DAYS_EMPLOYED)$")),
    ("Assets", "Car and real-estate ownership, car age.",
     re.compile(r"^(FLAG_OWN_CAR|FLAG_OWN_REALTY|OWN_CAR_AGE)$")),
    ("Building / housing attributes", "Normalised statistics about the applicant's building, in three flavours "
     "(_AVG, _MODE, _MEDI) per attribute: areas, floors, elevators, year built, wall material.",
     re.compile(r".*_(AVG|MODE|MEDI)$")),
    ("External scores", "Three normalised scores from external data sources.",
     re.compile(r"^EXT_SOURCE_\d+$")),
    ("Region and address consistency", "Region rating and population, plus flags for whether registered, "
     "living and work addresses differ.",
     re.compile(r"^(REGION_.*|REG_(REGION|CITY)_NOT_.*|LIVE_(REGION|CITY)_NOT_.*)$")),
    ("Contact flags", "Whether mobile, work phone, home phone, email etc. were provided.",
     re.compile(r"^FLAG_(MOBIL|EMP_PHONE|WORK_PHONE|CONT_MOBILE|PHONE|EMAIL)$")),
    ("Document flags", "FLAG_DOCUMENT_2..21: whether each document was provided.",
     re.compile(r"^FLAG_DOCUMENT_\d+$")),
    ("Social circle", "Observed and defaulted counts among the applicant's social surroundings (30 / 60 days).",
     re.compile(r"^(OBS|DEF)_\d+_CNT_SOCIAL_CIRCLE$")),
    ("Credit bureau enquiries", "Number of enquiries to the credit bureau (hour / day / week / month / quarter / year).",
     re.compile(r"^AMT_REQ_CREDIT_BUREAU_")),
    ("Application timing and history", "When the application was made and days since registration, ID "
     "document and last phone change.",
     re.compile(r"^(WEEKDAY_APPR_PROCESS_START|HOUR_APPR_PROCESS_START|DAYS_REGISTRATION|DAYS_ID_PUBLISH|"
                r"DAYS_LAST_PHONE_CHANGE)$")),
]


def column_group(name: str) -> str | None:
    for title, _, pattern in GROUPS:
        if pattern.match(name):
            return title
    return None


def group_counts(columns: list[str]) -> dict[str, list[str]]:
    """Columns per group; raises if any column is ungrouped. Pure."""
    out: dict[str, list[str]] = {title: [] for title, _, _ in GROUPS}
    for c in columns:
        g = column_group(c)
        if g is None:
            raise ValueError(f"column not assigned to a group: {c}")
        out[g].append(c)
    return out


def default_rate_by_category(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Rows and default rate (%) per category, missing shown as 'missing'. Pure."""
    key = df[col].fillna("missing").astype(str)
    g = df.groupby(key)["TARGET"]
    out = pd.DataFrame({"rows": g.size(), "default_rate_pct": g.mean() * 100.0})
    return out.sort_values("rows", ascending=False).reset_index(names=col)


def numeric_views(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Display-ready numeric series (age in years, years employed without the sentinel). Pure."""
    employed = df["DAYS_EMPLOYED"].where(df["DAYS_EMPLOYED"] != DAYS_EMPLOYED_SENTINEL)
    return {
        "AMT_INCOME_TOTAL (log10)": np.log10(df["AMT_INCOME_TOTAL"].clip(lower=1)),
        "AMT_CREDIT": df["AMT_CREDIT"],
        "AMT_ANNUITY": df["AMT_ANNUITY"],
        "AMT_GOODS_PRICE": df["AMT_GOODS_PRICE"],
        "Age (years, from DAYS_BIRTH)": -df["DAYS_BIRTH"] / 365.25,
        "Years employed (sentinel excluded)": -employed / 365.25,
        "EXT_SOURCE_1": df["EXT_SOURCE_1"],
        "EXT_SOURCE_2": df["EXT_SOURCE_2"],
        "EXT_SOURCE_3": df["EXT_SOURCE_3"],
    }


def plot_target_balance(df: pd.DataFrame, path: Path) -> None:
    counts = df["TARGET"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(["0 (repaid)", "1 (default)"], counts.to_numpy(), color=[COLORS[0], COLORS[1]])
    for bar, n in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, n, f"{n:,}\n({n / len(df):.2%})",
                ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Rows (train split)")
    ax.set_title("Target balance")
    ax.set_ylim(0, counts.max() * 1.18)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_column_types(df: pd.DataFrame, path: Path) -> None:
    numeric = df.select_dtypes("number")
    n_binary = int(sum(numeric[c].nunique() <= 2 for c in numeric))
    n_cat = df.select_dtypes("object").shape[1]
    parts = {
        "Categorical (text)": n_cat,
        "Numeric, 0/1 flags": n_binary,
        "Numeric, continuous or count": numeric.shape[1] - n_binary,
    }
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(list(parts), list(parts.values()), color="#4c72b0")
    for i, v in enumerate(parts.values()):
        ax.text(v + 0.5, i, str(v), va="center")
    ax.set_xlabel("Columns")
    ax.set_title(f"Column types ({df.shape[1]} columns)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_group_sizes(groups: dict[str, list[str]], path: Path) -> None:
    items = sorted(((k, len(v)) for k, v in groups.items()), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh([k for k, _ in items], [v for _, v in items], color="#4c72b0")
    for i, (_, v) in enumerate(items):
        ax.text(v + 0.3, i, str(v), va="center", fontsize=9)
    ax.set_xlabel("Columns")
    ax.set_title("Columns by topic (grouped by column name)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_default_rate_by_category(df: pd.DataFrame, path: Path) -> None:
    overall = df["TARGET"].mean() * 100
    fig, axes = plt.subplots(4, 2, figsize=(12, 15))
    for ax, col in zip(axes.ravel(), CATEGORY_PANELS):
        t = default_rate_by_category(df, col)
        ax.barh(t[col], t["default_rate_pct"], color="#4c72b0")
        ax.axvline(overall, color="#c44e52", linestyle="--", linewidth=1)
        for i, (r, n) in enumerate(zip(t["default_rate_pct"], t["rows"])):
            ax.text(r, i, f" {r:.1f}%  (n={n:,})", va="center", fontsize=7)
        ax.invert_yaxis()
        ax.set_title(col, fontsize=10)
        ax.set_xlim(0, max(t["default_rate_pct"].max() * 1.5, overall * 1.5))
        ax.tick_params(axis="y", labelsize=8)
    fig.suptitle(f"Default rate by category (dashed line = overall {overall:.2f}%)", y=0.995)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_numeric_distributions(df: pd.DataFrame, path: Path) -> None:
    views = numeric_views(df)
    fig, axes = plt.subplots(3, 3, figsize=(13, 10))
    for ax, (title, s) in zip(axes.ravel(), views.items()):
        lo, hi = s.quantile(0.005), s.quantile(0.995)
        bins = np.linspace(lo, hi, 50)
        for t in (0, 1):
            ax.hist(s[df["TARGET"] == t].dropna().clip(lo, hi), bins=bins, density=True,
                    alpha=0.55, color=COLORS[t], label=f"TARGET={t}")
        ax.set_title(f"{title}\nmissing: {s.isna().mean():.1%}", fontsize=9)
        ax.tick_params(labelsize=8)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Core numeric fields, density by TARGET (clipped to 0.5-99.5th percentile)", y=0.995)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def overview_markdown(df: pd.DataFrame, groups: dict[str, list[str]]) -> str:
    n, k = df.shape
    n_def = int(df["TARGET"].sum())
    n_obj = df.select_dtypes("object").shape[1]
    n_sentinel = int((df["DAYS_EMPLOYED"] == DAYS_EMPLOYED_SENTINEL).sum())
    lines = [
        "# Dataset overview (train split only)",
        "",
        "Home Credit Default Risk, `application_train.csv`: one row per loan application, one "
        "column per fact known at application time, plus the label. This file describes the 60% "
        "train split (`data/processed/train.csv`), generated by `src/data/eda.py`.",
        "",
        f"- Rows: {n:,}. Columns: {k} ({n_obj} text, {k - n_obj} numeric).",
        f"- Label: `TARGET`, 1 = default / payment difficulty. {n_def:,} of {n:,} rows "
        f"({n_def / n:.2%}) are 1.",
        "- Days columns (`DAYS_BIRTH`, `DAYS_EMPLOYED`, ...) are offsets relative to the application "
        "date, so negative numbers mean days before it. There is no calendar date anywhere.",
        f"- `DAYS_EMPLOYED` equals {DAYS_EMPLOYED_SENTINEL} (about 1,000 years) in {n_sentinel:,} rows "
        f"({n_sentinel / n:.1%}). It is a placeholder value, not a real duration, and is excluded in "
        "the years-employed chart.",
        f"- `CODE_GENDER` has {int((df['CODE_GENDER'] == 'XNA').sum())} rows coded `XNA`; "
        f"`ORGANIZATION_TYPE` has {int((df['ORGANIZATION_TYPE'] == 'XNA').sum()):,} rows coded `XNA`.",
        "- Missingness is covered in `missingness_summary.md` and `missingness_crosschecks.md`.",
        "",
        "## What the columns are",
        "",
        "| Topic | Columns | What it holds | Examples |",
        "|---|---|---|---|",
    ]
    desc = {t: d for t, d, _ in GROUPS}
    for title, cols in groups.items():
        lines.append(f"| {title} | {len(cols)} | {desc[title]} | {', '.join(f'`{c}`' for c in cols[:3])} |")
    lines += [
        "",
        "## Charts",
        "",
        "- `eda_target_balance.png`: class counts.",
        "- `eda_column_types.png`, `eda_column_groups.png`: column types and topics.",
        "- `eda_default_rate_by_category.png`: default rate per category for eight low-cardinality columns.",
        "- `eda_numeric_distributions.png`: nine core numeric fields, density split by TARGET.",
        "- `missingness_bar.png`: missing % per column (from 1.4).",
        "",
        "The columns charted are the core application fields shown for orientation. They are not a "
        "feature shortlist; that is 1.5.",
        "",
    ]
    return "\n".join(lines)


def run() -> None:
    df = pd.read_csv(TRAIN_PATH)
    groups = group_counts(list(df.columns))

    EDA_DIR.mkdir(parents=True, exist_ok=True)
    plot_target_balance(df, EDA_DIR / "eda_target_balance.png")
    plot_column_types(df, EDA_DIR / "eda_column_types.png")
    plot_group_sizes(groups, EDA_DIR / "eda_column_groups.png")
    plot_default_rate_by_category(df, EDA_DIR / "eda_default_rate_by_category.png")
    plot_numeric_distributions(df, EDA_DIR / "eda_numeric_distributions.png")
    (EDA_DIR / "dataset_overview.md").write_text(overview_markdown(df, groups), encoding="utf-8")

    print(f"Source: {TRAIN_PATH} ({len(df):,} rows, {df.shape[1]} columns)")
    print(f"Written to {EDA_DIR}")


if __name__ == "__main__":
    run()
