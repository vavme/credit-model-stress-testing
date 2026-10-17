"""Feature catalog and quirk checks (EDA session, Section 3).

Reads data/processed/train.csv ONLY, plus HomeCredit_columns_description.csv.
Writes reports/eda/feature_catalog.csv (one row per column) and
reports/eda/section3_facts.md (numbers behind the quirk checks). Descriptive
only: no WOE/IV, no models. Groups come from src.data.eda.GROUPS.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.eda import DAYS_EMPLOYED_SENTINEL, column_group, group_counts

SEED = 42
ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
DESC_PATH = ROOT / "data" / "raw" / "HomeCredit_columns_description.csv"
REPORT_DIR = ROOT / "reports" / "eda"
CATALOG_PATH = REPORT_DIR / "feature_catalog.csv"
FACTS_PATH = REPORT_DIR / "section3_facts.md"

APP_TABLE = "application_{train|test}.csv"
# Judgement overrides for columns the dtype rules cannot classify.
ORDINAL = {"NAME_EDUCATION_TYPE", "REGION_RATING_CLIENT", "REGION_RATING_CLIENT_W_CITY", "HOUR_APPR_PROCESS_START"}
COUNT_RE = re.compile(r"^(CNT_|AMT_REQ_CREDIT_BUREAU_|OBS_|DEF_)")
NEAR_CONSTANT_SHARE = 0.99


def load_descriptions(path: Path = DESC_PATH) -> dict[str, tuple[str, str]]:
    """Application-table column name -> (description, special). Pure apart from the read."""
    d = pd.read_csv(path, encoding="latin-1")
    d = d[d["Table"] == APP_TABLE]
    return {
        str(r["Row"]).strip(): (str(r["Description"]).strip(), "" if pd.isna(r["Special"]) else str(r["Special"]))
        for _, r in d.iterrows()
    }


def semantic_type(name: str, s: pd.Series) -> str:
    """Rule-based semantic type with a few named overrides. Pure."""
    if name == "SK_ID_CURR":
        return "ID"
    if name == "TARGET":
        return "target"
    if name in ORDINAL:
        return "ordinal"
    vals = set(s.dropna().unique().tolist())
    if s.dtype == object:
        return "binary flag" if len(vals) == 2 else "nominal"
    if vals <= {0, 1}:
        return "binary flag"
    if COUNT_RE.match(name):
        return "numeric count"
    return "numeric continuous"


def top_share(s: pd.Series) -> float:
    vc = s.value_counts(dropna=True)
    return float(vc.iloc[0] / vc.sum()) if len(vc) else float("nan")


def _fmt(x: float) -> str:
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.4g}"


def value_summary(s: pd.Series, n: int) -> str:
    if s.dtype == object:
        vc = s.value_counts(dropna=True).head(3)
        return "; ".join(f"{k} ({v / n:.1%})" for k, v in vc.items())
    return f"min {_fmt(s.min())} / median {_fmt(s.median())} / max {_fmt(s.max())}"


def column_notes(name: str, s: pd.Series, n: int) -> str:
    notes: list[str] = []
    miss = s.isna().mean()
    if miss > 0.5:
        notes.append(f"{miss:.0%} missing")
    elif miss > 0.05:
        notes.append(f"{miss:.0%} missing (>5%)")
    ts = top_share(s)
    if ts >= NEAR_CONSTANT_SHARE:
        notes.append(f"near-constant: top value {ts:.2%}")
    if name == "DAYS_EMPLOYED":
        k = int((s == DAYS_EMPLOYED_SENTINEL).sum())
        notes.append(f"placeholder {DAYS_EMPLOYED_SENTINEL} in {k:,} rows ({k / n:.1%})")
    if s.dtype == object and (s == "XNA").any():
        notes.append(f"XNA in {int((s == 'XNA').sum()):,} rows")
    if s.dtype != object and name.startswith("DAYS_") and name != "DAYS_EMPLOYED":
        notes.append("offset in days relative to application (negative = before)")
    if s.dtype != object and s.nunique() > 20:
        p99, mx, med = s.quantile(0.99), s.max(), s.median()
        if p99 > 0 and mx / p99 > 5:
            notes.append(f"extreme max: max {mx:,.4g} vs p99 {p99:,.4g}")
    return "; ".join(notes)


def build_catalog(df: pd.DataFrame, desc: dict[str, tuple[str, str]]) -> pd.DataFrame:
    n = len(df)
    rng = np.random.default_rng(SEED)
    rows = []
    for c in df.columns:
        s = df[c]
        nonnull = s.dropna().unique()
        ex = rng.choice(nonnull, size=min(3, len(nonnull)), replace=False) if len(nonnull) and c != "SK_ID_CURR" else []
        d, special = desc.get(c, ("(no entry in description file)", ""))
        rows.append(
            {
                "name": c,
                "group": column_group(c),
                "official_description": d + (f" [special: {special}]" if special else ""),
                "dtype": str(s.dtype),
                "semantic_type": semantic_type(c, s),
                "n_unique": int(s.nunique(dropna=True)),
                "missing_pct": round(float(s.isna().mean() * 100), 3),
                "value_summary": value_summary(s, n),
                "example_values": ", ".join(str(x) for x in ex),
                "notes": column_notes(c, s, n),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(TRAIN_PATH)
    n = len(df)
    desc = load_descriptions()
    cat = build_catalog(df, desc)
    cat.to_csv(CATALOG_PATH, index=False)

    out: list[str] = ["# Section 3 facts (train split only)", ""]

    # ---- groups ----
    gc = group_counts(list(df.columns))
    out += ["## Group counts", "", "| Group | Columns |", "|---|---|"]
    out += [f"| {g} | {len(c)} |" for g, c in gc.items()]
    out += [f"| **Total** | **{sum(len(c) for c in gc.values())}** (file has {df.shape[1]}) |", ""]
    out += ["## Semantic types", "", "| Type | Columns |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in cat["semantic_type"].value_counts().items()]
    out.append("")

    miss = df.isna().mean() * 100
    out += ["## Missingness headline (detail is Section 5)", "",
            f"- Columns with any missing value: {int((miss > 0).sum())} of {df.shape[1]}",
            f"- Columns with more than 5% missing: {int((miss > 5).sum())}; more than 50% missing: {int((miss > 50).sum())}", ""]

    # ---- description file coverage ----
    missing_desc = [c for c in df.columns if c not in desc]
    extra_desc = [k for k in desc if k not in df.columns]
    out += ["## Description file coverage", "",
            f"- Train columns without an entry in the description file: {missing_desc or 'none'}",
            f"- Description entries with no train column: {extra_desc or 'none'}", ""]

    # ---- quirk 1: DAYS_* ----
    out += ["## Quirk 1: DAYS_* columns", "", "| Column | min | median | max | % negative | % positive | % zero |", "|---|---|---|---|---|---|---|"]
    for c in [c for c in df.columns if c.startswith("DAYS_")]:
        s = df[c].dropna()
        out.append(f"| {c} | {s.min():,.0f} | {s.median():,.0f} | {s.max():,.0f} | {(s < 0).mean():.2%} | {(s > 0).mean():.2%} | {(s == 0).mean():.2%} |")
    out.append("")

    # ---- quirk 2: DAYS_EMPLOYED sentinel ----
    de = df["DAYS_EMPLOYED"]
    sent = de == DAYS_EMPLOYED_SENTINEL
    positives_other = int(((de > 0) & ~sent).sum())
    out += ["## Quirk 2: DAYS_EMPLOYED placeholder", "",
            f"- Rows equal to {DAYS_EMPLOYED_SENTINEL}: {int(sent.sum()):,} ({sent.mean():.2%}). Other positive values: {positives_other:,}.",
            f"- Distinct values among positives: {sorted(de[de > 0].unique().tolist())}",
            f"- Median of DAYS_EMPLOYED without the placeholder: {de[~sent].median():,.0f} days (min {de[~sent].min():,.0f}, max {de[~sent].max():,.0f}).",
            f"- Placeholder rows by NAME_INCOME_TYPE: {df.loc[sent, 'NAME_INCOME_TYPE'].value_counts().to_dict()}",
            f"- Placeholder rows with ORGANIZATION_TYPE = XNA: {int((df.loc[sent, 'ORGANIZATION_TYPE'] == 'XNA').sum()):,} of {int(sent.sum()):,}; XNA rows that are not placeholder: {int(((df['ORGANIZATION_TYPE'] == 'XNA') & ~sent).sum()):,}",
            f"- Default rate: placeholder rows {df.loc[sent, 'TARGET'].mean():.2%} (n={int(sent.sum()):,}) vs other rows {df.loc[~sent, 'TARGET'].mean():.2%} (n={int((~sent).sum()):,}).",
            f"- Pensioners with a real (non-placeholder) DAYS_EMPLOYED: {int(((df['NAME_INCOME_TYPE'] == 'Pensioner') & ~sent).sum()):,} of {int((df['NAME_INCOME_TYPE'] == 'Pensioner').sum()):,}", ""]

    # ---- quirk 3: XNA / unknown-like labels ----
    out += ["## Quirk 3: XNA and unknown-style labels in text columns", "", "| Column | XNA rows | % | other odd labels |", "|---|---|---|---|"]
    for c in df.select_dtypes(include="object").columns:
        k = int((df[c] == "XNA").sum())
        odd = {lab: int((df[c] == lab).sum()) for lab in ("Unknown", "not specified") if (df[c] == lab).any()}
        if k or odd:
            out.append(f"| {c} | {k:,} | {k / n:.2%} | {odd or ''} |")
    out.append("")

    # ---- quirk 4: outliers ----
    out += ["## Quirk 4: extreme values", "", "| Column | p50 | p99 | p99.9 | max | max / median |", "|---|---|---|---|---|---|"]
    for c in ["AMT_INCOME_TOTAL", "OBS_30_CNT_SOCIAL_CIRCLE", "DEF_30_CNT_SOCIAL_CIRCLE", "OBS_60_CNT_SOCIAL_CIRCLE", "DEF_60_CNT_SOCIAL_CIRCLE", "AMT_REQ_CREDIT_BUREAU_QRT", "CNT_CHILDREN", "AMT_CREDIT"]:
        s = df[c].dropna()
        med = s.median()
        out.append(f"| {c} | {med:,.0f} | {s.quantile(.99):,.0f} | {s.quantile(.999):,.0f} | {s.max():,.0f} | {s.max() / med if med else float('inf'):,.1f} |")
    inc = df["AMT_INCOME_TOTAL"]
    out += ["", f"- AMT_INCOME_TOTAL rows above 1,000,000: {int((inc > 1e6).sum()):,}; the largest 5 values: {inc.nlargest(5).tolist()}", ""]

    # ---- quirk 5: EXT_SOURCE ----
    num = df.select_dtypes(include=[np.number]).drop(columns=["SK_ID_CURR"])
    corr_t = num.corr()["TARGET"].drop("TARGET")
    rank = corr_t.abs().sort_values(ascending=False)
    out += ["## Quirk 5: EXT_SOURCE_* (missingness and signal)", "", "| Column | missing % | Pearson r with TARGET | rank by abs(r) of 104 numeric columns |", "|---|---|---|---|"]
    for c in ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]:
        out.append(f"| {c} | {df[c].isna().mean():.2%} | {corr_t[c]:+.4f} | {list(rank.index).index(c) + 1} |")
    out += ["", "Default rate by EXT_SOURCE quintile (quintiles on non-missing rows; n per bin):", ""]
    out += ["| Column | Q1 (lowest) | Q3 | Q5 (highest) | missing |", "|---|---|---|---|---|"]
    for c in ["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]:
        q = pd.qcut(df[c], 5, labels=False, duplicates="drop")
        g = df.groupby(q)["TARGET"].agg(["mean", "size"])
        miss = df[df[c].isna()]["TARGET"]
        out.append(f"| {c} | {g.loc[0, 'mean']:.2%} (n={int(g.loc[0, 'size']):,}) | {g.loc[2, 'mean']:.2%} (n={int(g.loc[2, 'size']):,}) | {g.loc[4, 'mean']:.2%} (n={int(g.loc[4, 'size']):,}) | {miss.mean():.2%} (n={len(miss):,}) |")
    out += ["", "Top 8 numeric columns by abs(Pearson r) with TARGET (pairwise complete):", ""]
    out += [f"- {c}: {corr_t[c]:+.4f}" for c in rank.head(8).index]
    out.append("")

    # ---- quirk 6: building AVG / MODE / MEDI ----
    stems = sorted({c.rsplit("_", 1)[0] for c in df.columns if re.search(r"_(AVG|MODE|MEDI)$", c) and c.endswith(("_AVG", "_MEDI"))})
    out += ["## Quirk 6: building columns in AVG / MODE / MEDI flavours", "",
            f"- Stems with an _AVG and _MEDI column: {len(stems)}. Building-group columns: {len(group_counts(list(df.columns))['Building / housing attributes'])}.", "",
            "| Stem | columns found | min corr among variants | identical missing mask |", "|---|---|---|---|"]
    for st in stems:
        cols = [c for c in (f"{st}_AVG", f"{st}_MODE", f"{st}_MEDI") if c in df.columns]
        numcols = [c for c in cols if df[c].dtype != object]
        cm = df[numcols].corr().to_numpy()
        same_mask = all(df[cols[0]].isna().equals(df[c].isna()) for c in cols[1:])
        out.append(f"| {st} | {len(cols)} | {cm[np.triu_indices_from(cm, 1)].min():.3f} | {same_mask} |")
    out += ["", f"- Building text columns (no AVG/MEDI twin): {[c for c in df.columns if c in ('FONDKAPREMONT_MODE','HOUSETYPE_MODE','WALLSMATERIAL_MODE','EMERGENCYSTATE_MODE')]}; numeric TOTALAREA_MODE.", ""]

    # ---- risky / redundant checks ----
    ts_all = {c: top_share(df[c]) for c in df.columns if c not in ("SK_ID_CURR",)}
    nearc = {c: round(v, 4) for c, v in sorted(ts_all.items(), key=lambda kv: -kv[1]) if v >= NEAR_CONSTANT_SHARE}
    out += ["## Near-constant columns (top value share >= 99% of non-missing)", "", f"{nearc or 'none'}", ""]
    pairs = [("AMT_CREDIT", "AMT_GOODS_PRICE"), ("AMT_ANNUITY", "AMT_CREDIT"), ("REGION_RATING_CLIENT", "REGION_RATING_CLIENT_W_CITY"),
             ("OBS_30_CNT_SOCIAL_CIRCLE", "OBS_60_CNT_SOCIAL_CIRCLE"), ("DEF_30_CNT_SOCIAL_CIRCLE", "DEF_60_CNT_SOCIAL_CIRCLE"),
             ("CNT_CHILDREN", "CNT_FAM_MEMBERS"), ("DAYS_BIRTH", "DAYS_EMPLOYED"), ("REG_REGION_NOT_LIVE_REGION", "REG_REGION_NOT_WORK_REGION"),
             ("LIVE_REGION_NOT_WORK_REGION", "REG_REGION_NOT_WORK_REGION"), ("REG_CITY_NOT_LIVE_CITY", "REG_CITY_NOT_WORK_CITY"),
             ("AMT_REQ_CREDIT_BUREAU_MON", "AMT_REQ_CREDIT_BUREAU_QRT")]
    out += ["## Pairs suspected to be redundant (Pearson r, pairwise complete)", "", "| A | B | r |", "|---|---|---|"]
    out += [f"| {a} | {b} | {df[a].corr(df[b]):+.3f} |" for a, b in pairs]
    flags = df[[c for c in df.columns if c.startswith("FLAG_DOCUMENT_")]]
    out += ["", f"- FLAG_DOCUMENT_* share of 1s: " + ", ".join(f"{c.replace('FLAG_DOCUMENT_', 'D')} {flags[c].mean():.2%}" for c in flags.columns), ""]

    # ---- completeness: columns a bank usually has ----
    probes = ["TERM", "RATE", "PURPOSE", "CHANNEL", "DEBT", "SAVING", "BALANCE", "DELINQ", "INSTAL", "PREV", "DATE"]
    out += ["## Completeness probe: column names containing typical bank fields", ""]
    out += [f"- '{p}': {[c for c in df.columns if p in c.upper()] or 'none'}" for p in probes]
    out.append("")

    FACTS_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
