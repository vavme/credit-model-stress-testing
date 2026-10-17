"""Feature shortlist PROPOSAL (EDA session, Section 7). Vav decides (tracker 1.5).

The picks and the one-line reasons below are written by hand from the Section 3, 5 and 6
results. This module only attaches the numbers, checks the proposal against the data, and
writes reports/eda/feature_shortlist.csv and reports/eda/section7_shortlist.md.

Reads data/processed/train.csv ONLY, plus the CSVs written by earlier sections
(feature_catalog.csv, bivariate_signal_ranking.csv, bivariate_binary_flags.csv,
categorical_summary.csv). Run those modules first.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.eda import DAYS_EMPLOYED_SENTINEL, column_group

ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
REPORT_DIR = ROOT / "reports" / "eda"

LOW, HIGH = 25, 40  # README: 25-40 feature shortlist

# (feature, one-line business reason). Core picks need no ruling from Vav.
CORE: list[tuple[str, str]] = [
    ("AMT_CREDIT", "Loan size: the exposure. Default rate by decile is hump-shaped, highest in the middle and lowest in the top decile."),
    ("AMT_ANNUITY", "Instalment size: what the client must pay each period. Hump-shaped like AMT_CREDIT, and a Spearman of about 0 hides it."),
    ("NAME_CONTRACT_TYPE", "Cash and revolving loans are different products with different risk (8.33% vs 5.62%)."),
    ("AMT_INCOME_TOTAL", "Capacity to repay. Needs a cap or log scale (max 117,000,000)."),
    ("DAYS_EMPLOYED", "Job tenure, a stability measure. Shorter tenure means higher default. Needs the 365243 placeholder replaced by missing plus a flag."),
    ("NAME_INCOME_TYPE", "Source of income. Working 9.52% vs Pensioner 5.40%. Pool the tiny categories (Student, Businessman, Maternity leave, Unemployed)."),
    ("OCCUPATION_TYPE", "Type of work, the widest spread of any category column (4.49% to 18.63%). 31% missing, mostly pensioners (structural)."),
    ("NAME_EDUCATION_TYPE", "Education level, an ordered scale lenders use as an income-stability proxy. 5.42% (higher) to 10.87% (lower secondary)."),
    ("NAME_HOUSING_TYPE", "Housing situation. Rented apartment 12.79% vs Office apartment 6.66%. A standard scorecard item."),
    ("FLAG_OWN_CAR", "Asset ownership. Owners 7.26% vs non-owners 8.49%. Kept instead of OWN_CAR_AGE (66% structural missing and an unexplained spike)."),
    ("EXT_SOURCE_1", "External score. Decile default rate falls from 16.88% to 2.62%. 56% missing and tracks age (r = -0.60). Provenance not documented."),
    ("EXT_SOURCE_2", "External score. Falls from 18.29% to 2.84%. Almost complete (0.22% missing). Provenance not documented."),
    ("EXT_SOURCE_3", "External score, the strongest single column (19.61% to 3.30%). 19.82% missing, nested with the bureau block. Provenance not documented."),
    ("REGION_RATING_CLIENT_W_CITY", "The lender's own region rating (1 to 3). Range 6.70 pp. Kept over REGION_RATING_CLIENT (r = 0.95 between them)."),
    ("REGION_POPULATION_RELATIVE", "Urban density of the region. Range 5.31 pp. Only moderately related to the region rating (r about -0.53)."),
    ("REG_CITY_NOT_LIVE_CITY", "Registered city differs from living city: an address-stability signal. 12.34% vs 7.71%."),
    ("REG_CITY_NOT_WORK_CITY", "Registered city differs from work city. 10.63% vs 7.31%. Only r = 0.44 with the item above."),
    ("DAYS_REGISTRATION", "Time since the client changed registration: residential stability. Range 4.18 pp."),
    ("DAYS_ID_PUBLISH", "Time since the ID document was changed. Range 4.29 pp."),
    ("DAYS_LAST_PHONE_CHANGE", "Time since last phone change: contact stability. Range 4.40 pp. 12.1% of rows are 0."),
    ("FLAG_WORK_PHONE", "A work phone was given. 9.61% vs 7.69%. Easy to explain."),
    ("AMT_REQ_CREDIT_BUREAU_QRT", "Credit enquiries in the last quarter: recent credit seeking. Weak alone (range 1.68 pp), but a standard bank item. Its 13.48% natural missing is informative (Section 5)."),
    ("AMT_REQ_CREDIT_BUREAU_YEAR", "Credit enquiries in the last year. Weak alone (range 1.35 pp). Shares the missing block with the item above."),
    ("FLOORSMAX_AVG", "Building height, a housing-quality proxy. Largest Spearman of the building columns (-0.045); range 4.24 pp. 49.69% missing."),
    ("LIVINGAREA_AVG", "Living area of the building. Range 3.56 pp. One flavour only (AVG, MEDI and MODE correlate at 0.97 or more)."),
    ("WALLSMATERIAL_MODE", "Wall material, the one text building column with a wide spread (Wooden 9.81% vs Monolithic 4.43%). 50.77% missing."),
]

# Included, but each needs a ruling from Vav before it is final.
PENDING: list[tuple[str, str]] = [
    ("DAYS_BIRTH", "Age. The strongest non-EXT column (Spearman +0.078; younger defaults more). Sensitive attribute: dropping it costs signal, and EXT_SOURCE_1 partly brings it back."),
    ("NAME_FAMILY_STATUS", "Marital status. Single 9.92% vs Widow 5.89%. Sensitive attribute in many jurisdictions (not verified for Home Credit's markets)."),
]

# Excluded by default, but plausible if Vav rules otherwise.
OPTIONS: dict[str, str] = {
    "CODE_GENDER": "Sensitive attribute (M 10.13% vs F 7.01%). Excluded by default because many lenders cannot use gender. Your ruling.",
    "ORGANIZATION_TYPE": "Strong spread (7.46 pp) but 58 categories, 41 of them rare, and XNA (18.01%) is the same rows as the DAYS_EMPLOYED placeholder. Needs grouping.",
    "AMT_GOODS_PRICE": "r = 0.987 with AMT_CREDIT, and an unexplained clump at 450,000 (15,614 rows, 13.67% default). Excluded as a near-duplicate.",
    "OWN_CAR_AGE": "66% missing (structural: no car) and an unexplained spike at ages 64 and 65 (1,992 rows). Needs your view on the spike.",
    "FLAG_DOCUMENT_3": "+2.64 pp with 71% ones, so it has real spread. Which document it is is not documented, and 'provided' may be recorded after the decision (hypothesis).",
    "FLAG_DOCUMENT_6": "-2.72 pp, 8.79% ones. Same uncertainty about meaning and timing as FLAG_DOCUMENT_3.",
    "DEF_30_CNT_SOCIAL_CIRCLE": "Strongest social-circle column (range 5.85 pp). When those defaults were observed relative to this loan is not documented (leakage hypothesis), and it scores people by their contacts.",
}

# Reasons for explicit exclusions that are not options.
EXCLUDE: dict[str, str] = {
    "SK_ID_CURR": "Identifier, not a feature.",
    "TARGET": "The label.",
    "CNT_CHILDREN": "Weak (range 1.77 pp), max 19, and a family-status attribute.",
    "CNT_FAM_MEMBERS": "Weak (range 1.49 pp) and r = 0.88 with CNT_CHILDREN.",
    "NAME_TYPE_SUITE": "Who accompanied the client. Weak (2.55 pp range) and 4 of 8 categories are rare.",
    "FLAG_OWN_REALTY": "Near noise: 7.97% vs 8.30% (0.32 pp).",
    "FLAG_MOBIL": "Near-constant: 184,505 of 184,506 rows are 1.",
    "FLAG_CONT_MOBILE": "Near-constant (99.81% are 1).",
    "FLAG_EMP_PHONE": "Duplicates the pensioner pattern already carried by NAME_INCOME_TYPE and the DAYS_EMPLOYED placeholder (r = 0.62 with age).",
    "FLAG_PHONE": "Weak (-1.44 pp).",
    "FLAG_EMAIL": "No signal: 8.03% vs 8.08%.",
    "REGION_RATING_CLIENT": "r = 0.95 with REGION_RATING_CLIENT_W_CITY, which is kept.",
    "REG_REGION_NOT_LIVE_REGION": "Rare (1.53% are 1) and weaker than the city-level version.",
    "REG_REGION_NOT_WORK_REGION": "Rare (5.13% are 1), weak (+0.86 pp) and r = 0.86 with LIVE_REGION_NOT_WORK_REGION.",
    "LIVE_REGION_NOT_WORK_REGION": "Rare, weak (+0.38 pp), r = 0.86 with REG_REGION_NOT_WORK_REGION.",
    "LIVE_CITY_NOT_WORK_CITY": "r = 0.83 with REG_CITY_NOT_WORK_CITY, which is kept.",
    "WEEKDAY_APPR_PROCESS_START": "Near noise (0.53 pp range) and not a borrower attribute.",
    "HOUR_APPR_PROCESS_START": "Application-process timing, not a borrower attribute. Modest spread (3.05 pp).",
    "OBS_30_CNT_SOCIAL_CIRCLE": "Weak (range 1.12 pp) and r = 0.999 with OBS_60.",
    "OBS_60_CNT_SOCIAL_CIRCLE": "Weak and r = 0.999 with OBS_30.",
    "DEF_60_CNT_SOCIAL_CIRCLE": "r = 0.86 with DEF_30 (an option, see above).",
    "AMT_REQ_CREDIT_BUREAU_HOUR": "Near-constant (99.41% are 0).",
    "AMT_REQ_CREDIT_BUREAU_DAY": "Near-constant (99.45% are 0).",
    "AMT_REQ_CREDIT_BUREAU_WEEK": "No signal (range 0.08 pp).",
    "AMT_REQ_CREDIT_BUREAU_MON": "Weak (range 1.44 pp). QRT and YEAR already cover recent enquiries.",
}

BUILDING_REASON = ("Building block: at most one flavour per stem, and only 3 representatives kept. The rest are AVG / MODE / MEDI twins "
                   "(r >= 0.965 within a stem) or cross-stem near-duplicates (r up to 0.94), with 47 to 70% missing.")
DOC_CONST_REASON = "Document flag: at least 99% one value, so bins would hold a handful of defaults."
DOC_OTHER_REASON = "Document flag: which document it is is not documented, and 'provided' may be recorded after the decision (hypothesis)."


def top_share(s: pd.Series) -> float:
    vc = s.value_counts(dropna=True)
    return float(vc.iloc[0] / vc.sum())


def validate(core: list[str], pending: list[str], options: list[str], excluded: list[str], all_cols: list[str]) -> list[str]:
    """Problems with the proposal; an empty list means it is consistent. Pure."""
    problems = []
    chosen = core + pending
    if not LOW <= len(chosen) <= HIGH:
        problems.append(f"shortlist has {len(chosen)} features, outside {LOW}-{HIGH}")
    for name, lst in [("core", core), ("pending", pending), ("options", options), ("excluded", excluded)]:
        if len(set(lst)) != len(lst):
            problems.append(f"duplicates in {name}")
    sets = [set(core), set(pending), set(options), set(excluded)]
    for i in range(4):
        for j in range(i + 1, 4):
            if sets[i] & sets[j]:
                problems.append(f"overlap: {sorted(sets[i] & sets[j])}")
    covered = set().union(*sets)
    if covered != set(all_cols):
        problems.append(f"not covered: {sorted(set(all_cols) - covered)}; unknown: {sorted(covered - set(all_cols))}")
    return problems


def main() -> None:
    df = pd.read_csv(TRAIN_PATH)
    n = len(df)
    cols = list(df.columns)
    cat = pd.read_csv(REPORT_DIR / "feature_catalog.csv").set_index("name")
    rank = pd.read_csv(REPORT_DIR / "bivariate_signal_ranking.csv").set_index("feature")
    flags = pd.read_csv(REPORT_DIR / "bivariate_binary_flags.csv").set_index("feature")
    catsum = pd.read_csv(REPORT_DIR / "categorical_summary.csv")

    core_names = [c for c, _ in CORE]
    pend_names = [c for c, _ in PENDING]
    reason = {**dict(CORE), **dict(PENDING), **OPTIONS, **EXCLUDE}
    status = {c: "shortlist" for c in core_names}
    status.update({c: "shortlist (needs ruling)" for c in pend_names})
    status.update({c: "excluded (option, needs ruling)" for c in OPTIONS})
    status.update({c: "excluded" for c in EXCLUDE})
    for c in cols:
        if c in status:
            continue
        g = column_group(c)
        if g == "Building / housing attributes":
            status[c], reason[c] = "excluded", BUILDING_REASON
        elif c.startswith("FLAG_DOCUMENT_"):
            status[c] = "excluded"
            reason[c] = DOC_CONST_REASON if top_share(df[c]) >= 0.99 else DOC_OTHER_REASON
    options = list(OPTIONS)
    excluded = [c for c in cols if status.get(c) == "excluded"]
    problems = validate(core_names, pend_names, options, excluded, cols)
    if problems:
        raise SystemExit("Shortlist problems: " + "; ".join(problems))

    def evidence(c: str) -> str:
        if c in rank.index:
            r = rank.loc[c]
            return f"range {r['range_pp']:.2f} pp (shuffled {r['null_range_pp']:.2f}); Spearman {r['spearman_with_target']:+.3f}"
        if c in flags.index:
            return f"rate when 1 {flags.loc[c, 'rate_when_1_pct']:.2f}% vs 0 {flags.loc[c, 'rate_when_0_pct']:.2f}%"
        t = catsum[(catsum["column"] == c) & (catsum["n"] >= 1000)]
        if len(t):
            return f"category rates {t['rate_pct'].min():.2f}% to {t['rate_pct'].max():.2f}% (n >= 1,000)"
        return ""

    rows = []
    for c in cols:
        rows.append({"feature": c, "group": column_group(c), "status": status[c], "type": cat.loc[c, "semantic_type"],
                     "missing_pct": cat.loc[c, "missing_pct"], "evidence_train": evidence(c), "reason": reason[c]})
    out_df = pd.DataFrame(rows)
    out_df.to_csv(REPORT_DIR / "feature_shortlist.csv", index=False)

    # ---------- checks on the shortlist itself (train only)
    chosen = core_names + pend_names
    num = [c for c in chosen if df[c].dtype != object]
    clean = pd.DataFrame({c: (df[c].where(df[c] != DAYS_EMPLOYED_SENTINEL) if c == "DAYS_EMPLOYED" else df[c]) for c in num})
    corr = clean.corr()
    iu = np.triu_indices_from(corr.to_numpy(), 1)
    pairs = sorted(zip(np.abs(corr.to_numpy()[iu]), corr.index[iu[0]], corr.columns[iu[1]]), reverse=True)
    core_only = [c for c in core_names if c in num]
    cc = clean[core_only].corr()
    iu2 = np.triu_indices_from(cc.to_numpy(), 1)
    max_core = max(np.abs(cc.to_numpy()[iu2]))
    miss = df[chosen].isna().mean() * 100
    sh = out_df[out_df["status"].str.startswith("shortlist")]
    grp = sh.groupby("group").size().reindex(
        [g for g in out_df["group"].unique()], fill_value=0)
    totals = out_df.groupby("group").size()

    md = ["# Section 7: feature shortlist (proposal)", "",
          "This is a proposal. Vav decides (tracker 1.5). Nothing here is written to `docs/decisions/`. Generated by `src/data/shortlist.py`; the picks and reasons are written by hand from Sections 3, 5 and 6. Labels: [DATA] verified on the train split.", "",
          f"## Proposal: {len(chosen)} features ({len(core_names)} core + {len(pend_names)} that need your ruling)", "",
          "| # | Feature | Group | Type | Missing % | Evidence [DATA] | Why a bank would care |", "|---|---|---|---|---|---|---|"]
    for i, c in enumerate(chosen, 1):
        tag = " **(ruling)**" if c in pend_names else ""
        md.append(f"| {i} | {c}{tag} | {column_group(c)} | {cat.loc[c, 'semantic_type']} | {cat.loc[c, 'missing_pct']:.2f} | {evidence(c)} | {reason[c]} |")
    md += ["", "## Checks on the proposal [DATA]", "",
           f"- Count: {len(chosen)} (README range {LOW} to {HIGH}). If you drop both ruling items it is {len(core_names)}, still inside the range.",
           f"- Largest absolute Pearson correlation between two shortlisted numeric columns: {pairs[0][0]:.3f} ({pairs[0][1]} and {pairs[0][2]}). Next: " + "; ".join(f"{a:.2f} ({b}, {c_})" for a, b, c_ in pairs[1:4]) + f". Among core picks only: {max_core:.3f}.",
           f"- Natural missing above 5% in the shortlist: {int((miss > 5).sum())} of {len(chosen)} ({', '.join(miss[miss > 5].index)}). Fully observed: {int((miss == 0).sum())} of {len(chosen)}.",
           f"- Needs a treatment step (placeholder, cap or pooling): DAYS_EMPLOYED (placeholder), AMT_INCOME_TOTAL (cap or log), NAME_INCOME_TYPE (pool rare categories), plus the 8 columns with natural missing above 5%.",
           "- Not tested here: how much each feature adds in a model. That belongs to later phases. The evidence column is one-column-at-a-time.", "",
           "### Group coverage", "", "| Group | Columns | On the shortlist |", "|---|---|---|"]
    md += [f"| {g} | {int(totals[g])} | {int(grp[g])} |" for g in grp.index]
    md += ["", "No feature is picked from Social circle or Document flags by default. Both are options below.", "",
           "## Excluded but plausible: options that need your ruling", "", "| Feature | Why it is out by default |", "|---|---|"]
    md += [f"| {c} | {r} |" for c, r in OPTIONS.items()]
    md += ["", "Optional engineered features (not counted above, and adding features beyond the shortlist needs your OK): payment-to-income (AMT_ANNUITY / AMT_INCOME_TOTAL), credit-to-income (AMT_CREDIT / AMT_INCOME_TOTAL), and implied term (AMT_CREDIT / AMT_ANNUITY). Banks use all three. Implied term is a hypothesis, since the data has no term column.", ""]
    ex = out_df[out_df["status"] == "excluded"]
    md += [f"## Excluded: {len(ex)} columns", "", "Full list with reasons: `feature_shortlist.csv`. Summary by reason:", "", "| Reason | Columns |", "|---|---|"]
    for r, g in ex.groupby("reason"):
        names = g["feature"].tolist()
        md.append(f"| {r} | {len(names)}: {', '.join(names) if len(names) <= 6 else ', '.join(names[:4]) + ', ...'} |")
    md += ["", "## Risks to flag", "",
           "- **EXT_SOURCE_1/2/3 carry most of the signal** (Section 6) and their source and timing are not documented. If they contain information from after origination, every result is inflated. Hypothesis, not verified.",
           "- **Sensitive attributes.** DAYS_BIRTH and NAME_FAMILY_STATUS are in; CODE_GENDER is out. Dropping both ruling items leaves 26 features, but EXT_SOURCE_1 correlates -0.60 with age.",
           "- **Eight shortlisted columns have natural missing above 5%.** Scenario A corrupts on top of that (Section 5).",
           "- **The shortlist is built on train only, one column at a time.** Two columns that look weak alone can still help in a model.", ""]
    (REPORT_DIR / "section7_shortlist.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
