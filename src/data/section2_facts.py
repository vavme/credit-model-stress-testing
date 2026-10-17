"""Train-only facts backing the Section 2 dataset explanation (EDA session).

Reads data/processed/train.csv ONLY, plus the column description file (a
documentation file, not one of the auxiliary data tables). Writes
reports/eda/section2_facts.md. Numbers only; the narrative lives in
reports/eda/section2_dataset.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
DESC_PATH = ROOT / "data" / "raw" / "HomeCredit_columns_description.csv"
OUT_PATH = ROOT / "reports" / "eda" / "section2_facts.md"


def pct(n: int, total: int) -> str:
    return f"{n:,} ({n / total:.2%})"


def main() -> None:
    df = pd.read_csv(TRAIN_PATH)
    n = len(df)
    desc = pd.read_csv(DESC_PATH, encoding="latin-1")
    out: list[str] = ["# Section 2 facts (train split only)", ""]

    out += ["## Documentation file: rows per table", "", "| Table | Documented columns |", "|---|---|"]
    for table, cnt in desc["Table"].value_counts().items():
        out.append(f"| {table} | {cnt} |")
    target_desc = desc.loc[desc["Row"] == "TARGET", "Description"].iloc[0]
    out += ["", f"TARGET description (quoted from file): {target_desc}", ""]

    out += ["## Unit of observation", ""]
    out.append(f"- Rows: {n:,}. Unique SK_ID_CURR: {df['SK_ID_CURR'].nunique():,}.")
    cal = [c for c in df.columns if any(k in c.upper() for k in ("DATE", "MONTH", "YEAR_", "TIMESTAMP"))]
    out.append(f"- Columns with calendar-style names (date, month, timestamp): {cal if cal else 'none'}.")
    days = [c for c in df.columns if c.startswith("DAYS_")]
    out.append(f"- DAYS_* columns: {days}. Only WEEKDAY_APPR_PROCESS_START and HOUR_APPR_PROCESS_START describe application timing (day of week, hour).")
    out.append(f"- Application weekday counts: {df['WEEKDAY_APPR_PROCESS_START'].value_counts().to_dict()}")
    out.append("")

    out += ["## Who the borrowers are (train)", ""]
    age = -df["DAYS_BIRTH"] / 365.25
    out.append(f"- Age in years: min {age.min():.1f}, median {age.median():.1f}, max {age.max():.1f}.")
    out.append(f"- AMT_INCOME_TOTAL: median {df['AMT_INCOME_TOTAL'].median():,.0f}, mean {df['AMT_INCOME_TOTAL'].mean():,.0f}. Currency is not stated in the data or the description file.")
    out.append(f"- AMT_CREDIT: median {df['AMT_CREDIT'].median():,.0f}.")
    for col in ["NAME_CONTRACT_TYPE", "CODE_GENDER", "NAME_INCOME_TYPE", "NAME_EDUCATION_TYPE", "NAME_FAMILY_STATUS", "FLAG_OWN_CAR", "FLAG_OWN_REALTY"]:
        vc = df[col].value_counts(dropna=False)
        out.append(f"- {col}: " + "; ".join(f"{k} {pct(v, n)}" for k, v in vc.items()))
    out.append("")

    out += ["## TARGET (train)", ""]
    out.append(f"- TARGET = 1: {pct(int(df['TARGET'].sum()), n)}; TARGET = 0: {pct(int((df['TARGET'] == 0).sum()), n)}.")
    out.append("- Default rate by NAME_CONTRACT_TYPE (train): " + "; ".join(
        f"{k} {v:.2%} (n={int(c):,})"
        for (k, v), c in zip(df.groupby("NAME_CONTRACT_TYPE")["TARGET"].mean().items(),
                             df.groupby("NAME_CONTRACT_TYPE").size())))
    out.append("- Columns that look like a loan outcome or approval status (STATUS, APPROVED, REFUSED, WRITE): "
               + str([c for c in df.columns if any(k in c.upper() for k in ("STATUS", "APPROV", "REFUS", "WRITE", "DPD"))]))
    out.append("")

    OUT_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
