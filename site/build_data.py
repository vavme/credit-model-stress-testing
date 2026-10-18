"""Site build, stage 1: aggregate the EDA into JSON for the static site.

Run from the repo root:   python -m poetry run python site/build_data.py

Reads data/processed/train.csv ONLY (never val.csv, test.csv or the split indices), plus the
train-derived EDA outputs in reports/eda/ and the column description file. Writes aggregated JSON
to site/data/ (facts.json, features.json, charts.json, content.json) and a local review table to
docs/site_facts_table.md (gitignored). No row-level data is written.

Every number on the site is a fact in facts.json: computed here from the train split, parsed from an
EDA output, or (for the AI-drafted predictions) entered by hand and verified to appear in its source
file. The registry of all numbers found in the EDA outputs is stored too, for the copy check.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.corruption_candidates_facts import label_flip_table  # noqa: E402
from src.data.eda import DAYS_EMPLOYED_SENTINEL, column_group  # noqa: E402
from src.data.missingness_baseline import cluster_label, mask_clusters, phi_matrix  # noqa: E402
from src.data.split import SEED  # noqa: E402

SITE = ROOT / "site"
DATA_DIR = SITE / "data"
EDA = ROOT / "reports" / "eda"
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
DESC_PATH = ROOT / "data" / "raw" / "HomeCredit_columns_description.csv"
FACTS_TABLE = ROOT / "docs" / "site_facts_table.md"

MIN_CELL = 10  # categories, bins and values with fewer rows are suppressed
HIST_BINS = 30
SENSITIVE = {"CODE_GENDER", "DAYS_BIRTH", "NAME_FAMILY_STATUS", "CNT_CHILDREN", "CNT_FAM_MEMBERS"}
CANDIDATE_FEATURES = {"EXT_SOURCE_2", "AMT_INCOME_TOTAL", "AMT_CREDIT", "AMT_ANNUITY", "DAYS_EMPLOYED", "TARGET"}
STATUS_MAP = {"shortlist": "shortlist", "shortlist (needs ruling)": "shortlist_ruling",
              "excluded (option, needs ruling)": "option", "excluded": "excluded"}

FORMATS = {
    "int": lambda v: f"{int(round(v)):,}",
    "p0": lambda v: f"{v:.0f}%", "p1": lambda v: f"{v:.1f}%", "p2": lambda v: f"{v:.2f}%",
    "f1": lambda v: f"{v:.1f}", "f2": lambda v: f"{v:.2f}", "f3": lambda v: f"{v:.3f}", "f4": lambda v: f"{v:.4f}",
    "s3": lambda v: f"{v:+.3f}", "raw": lambda v: str(v),
}


class Facts:
    """Collects every number shown on the site with its label and source."""

    def __init__(self, eda_blob: str) -> None:
        self.items: dict[str, dict] = {}
        self.eda_blob = eda_blob

    def add(self, key: str, value, fmt: str, source: str, how: str, label: str = "DATA", verify_in: str | None = None) -> str:
        assert key not in self.items, f"duplicate fact {key}"
        text = FORMATS[fmt](value)
        bare = text.rstrip("%")
        found = text in self.eda_blob or bare in self.eda_blob
        if verify_in is not None:
            assert text in verify_in or bare in verify_in, f"{key}: {text} not found in its source text"
        self.items[key] = {"value": float(value) if isinstance(value, (int, float, np.integer, np.floating)) else value,
                           "text": text, "bare": bare, "label": label, "source": source, "how": how,
                           "in_eda_text": found}
        return text

    def t(self, key: str) -> str:
        return self.items[key]["text"]

    def v(self, key: str):
        return self.items[key]["value"]


def ascii_clean(s: str) -> str:
    """Kaggle description file has stray non-ASCII bytes (read as latin-1). Replace them with an ellipsis."""
    s = re.sub(r"[^\x00-\x7f]+", "...", s)
    return re.sub(r"\s*\[special: (.*?)\]\s*$", r" (Kaggle note: \1)", s)


def num_tokens(text: str) -> set[str]:
    return {m.rstrip(".,").lstrip("+-") for m in re.findall(r"[+-]?\d[\d,]*\.?\d*", text)}


def r6(x: float) -> float:
    return float(f"{x:.6g}")


def parse_integrity(text: str) -> dict:
    out = {}
    m = re.search(r"Rows x columns \| ([\d,]+) x (\d+)", text)
    out["n_raw"], out["n_cols"] = int(m.group(1).replace(",", "")), int(m.group(2))
    for key, label in (("dup_rows", "Duplicate rows"), ("dup_loan_numbers", "Duplicate SK_ID_CURR"), ("target_missing", "TARGET missing")):
        out[key] = int(re.search(rf"\| {label} \| ([\d,]+) \|", text).group(1).replace(",", ""))
    for name in ("train", "val", "test"):
        m = re.search(rf"^\| {name} \| ([\d,]+) \| ([\d.]+)% \| ([\d,]+) \| ([\d.]+)% \|", text, re.M)
        out[name] = {"rows": int(m.group(1).replace(",", "")), "pos": int(m.group(3).replace(",", "")), "rate": float(m.group(4))}
    return out


def distribution(name: str, s: pd.Series, stype: str) -> dict:
    """Aggregated distribution of one column. Cells under MIN_CELL rows are merged into 'other'. Pure."""
    n_missing = int(s.isna().sum())
    if stype in ("ID",):
        return {"kind": "none"}
    if s.dtype == object or stype == "target":
        vc = s.fillna("(missing)").astype(str).value_counts()
        keep = vc[vc >= MIN_CELL]
        other = int(vc[vc < MIN_CELL].sum())
        rows = [{"label": k, "n": int(v)} for k, v in keep.head(14).items()]
        rest = int(keep.iloc[14:].sum()) + other
        if rest:
            rows.append({"label": "other (small categories merged)", "n": rest})
        return {"kind": "cats", "rows": rows, "n_missing": n_missing}
    if stype == "binary flag":
        vc = s.value_counts()
        return {"kind": "cats", "rows": [{"label": str(int(k)), "n": int(v)} for k, v in sorted(vc.items())], "n_missing": n_missing}
    x = s.where(s != DAYS_EMPLOYED_SENTINEL) if name == "DAYS_EMPLOYED" else s
    vals = x.dropna()
    extra = {"n_missing": n_missing}
    if name == "DAYS_EMPLOYED":
        extra["n_placeholder"] = int((s == DAYS_EMPLOYED_SENTINEL).sum())
    if vals.nunique() <= 30:
        vc = vals.value_counts().sort_index()
        keep = vc[vc >= MIN_CELL]
        rows = [{"label": f"{k:g}", "n": int(v)} for k, v in keep.items()]
        if (vc < MIN_CELL).any():
            rows.append({"label": "rare values merged", "n": int(vc[vc < MIN_CELL].sum())})
        return {"kind": "values", "rows": rows, **extra}
    lo, hi = float(vals.quantile(0.005)), float(vals.quantile(0.995))
    if lo == hi:
        lo, hi = float(vals.min()), float(vals.max())
    edges = np.linspace(lo, hi, HIST_BINS + 1)
    counts, _ = np.histogram(vals.clip(lo, hi), bins=edges)
    return {"kind": "hist", "edges": [r6(e) for e in edges], "counts": [int(c) for c in counts],
            "below": int((vals < lo).sum()), "above": int((vals > hi).sum()), **extra}


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(TRAIN_PATH)
    n = len(df)
    y = df["TARGET"].to_numpy()
    cols = list(df.columns)

    eda_md = {p.name: p.read_text(encoding="utf-8") for p in EDA.glob("*.md")}
    eda_blob = "\n".join(eda_md.values())
    cat = pd.read_csv(EDA / "feature_catalog.csv")
    shortlist = pd.read_csv(EDA / "feature_shortlist.csv")
    ranking = pd.read_csv(EDA / "bivariate_signal_ranking.csv")
    bins = pd.read_csv(EDA / "bivariate_numeric_bins.csv")
    catsum = pd.read_csv(EDA / "categorical_summary.csv")
    flags = pd.read_csv(EDA / "bivariate_binary_flags.csv")
    mfeat = pd.read_csv(EDA / "missingness_by_feature.csv")
    mgroup = pd.read_csv(EDA / "missingness_by_group.csv")
    corr_t = pd.read_csv(EDA / "correlation_with_target.csv")
    numsum = pd.read_csv(EDA / "numeric_summary.csv")
    desc = pd.read_csv(DESC_PATH, encoding="latin-1")
    integ = parse_integrity(eda_md["section1_integrity.md"])
    cand_md = eda_md["section8_corruption_candidates.md"]

    F = Facts(eda_blob)
    S1, S4, S5 = "reports/eda/section1_integrity.md", "reports/eda/section4_target.md", "reports/eda/section5_facts.md"
    TR = "train split (data/processed/train.csv)"

    # ------------------------------------------------------------ dataset and split
    assert integ["train"]["rows"] == n, "train.csv does not match the integrity report"
    F.add("n_raw", integ["n_raw"], "int", S1, "parsed from the integrity report (full-file structural check)")
    F.add("n_train", n, "int", TR, "row count")
    F.add("n_cols", len(cols), "int", TR, "column count")
    for sp in ("val", "test"):
        F.add(f"n_{sp}", integ[sp]["rows"], "int", S1, "parsed (size only)")
        F.add(f"pos_{sp}", integ[sp]["pos"], "int", S1, "parsed (default count only)")
        F.add(f"rate_{sp}_pct", integ[sp]["rate"], "f4", S1, "parsed (TARGET rate only)")
    for sp in ("train", "val", "test"):
        F.add(f"{sp}_share_pct", integ[sp]["rows"] / integ["n_raw"] * 100, "p0", S1, "split size divided by the file total")
    F.add("dup_rows", integ["dup_rows"], "int", S1, "parsed (full-file structural check)")
    F.add("dup_loan_numbers", integ["dup_loan_numbers"], "int", S1, "parsed (full-file structural check)")
    F.add("target_missing", integ["target_missing"], "int", S1, "parsed (full-file structural check)")
    F.add("min_cell", MIN_CELL, "int", "site/build_data.py", "smallest group size shown on the site")
    F.add("seed", SEED, "raw", "src/data/split.py", "constant in the split module")
    F.add("n_aux_tables", int(desc["Table"].nunique() - 1), "int", "data/raw/HomeCredit_columns_description.csv", "tables documented besides the application table", "DOC")

    # ------------------------------------------------------------ target and imbalance
    npos = int(y.sum())
    F.add("n_pos", npos, "int", TR, "count of TARGET = 1")
    F.add("waffle_total", 100, "int", "site copy", "squares in the waffle chart")
    F.add("waffle_filled", int(round(npos / n * 100)), "int", TR, "default rate rounded to whole squares")
    F.add("n_neg", n - npos, "int", TR, "count of TARGET = 0")
    F.add("default_rate_pct", npos / n * 100, "p2", TR, "mean of TARGET")
    F.add("rate_train_pct", integ["train"]["rate"], "f4", S1, "parsed")
    F.add("imbalance_ratio", (n - npos) / npos, "f2", TR, "zeros divided by ones")
    F.add("acc_all_zero_pct", (n - npos) / n * 100, "p2", TR, "accuracy of predicting 0 for every row")
    F.add("auc_useless", roc_auc_score(y, np.zeros(n)), "f2", TR, "AUC of a constant score")
    F.add("ap_floor", average_precision_score(y, np.zeros(n)), "f4", TR, "PR-AUC of a constant score, equals the default rate")
    flip = label_flip_table(n, npos)
    for r in flip.itertuples():
        pct = int(round(r.severity * 100))
        if pct:
            F.add(f"hide_{pct}_rate_pct", r.default_rate_pct, "p2", TR, "arithmetic: default rate if that share of defaults is recorded as 0")
            F.add(f"hide_{pct}_ratio", r.ratio_0_to_1, "f1", TR, "arithmetic: zeros per one after hiding")

    # ------------------------------------------------------------ data at a glance
    types = cat["semantic_type"].value_counts()
    for k, v in types.items():
        F.add("n_type_" + k.replace(" ", "_").replace("ID", "identifier"), int(v), "int", "reports/eda/feature_catalog.csv", "count of columns by semantic type")
    groups = cat["group"].value_counts()
    for g, v in groups.items():
        F.add("n_group_" + re.sub(r"[^a-z]+", "_", g.lower().replace("id and", "identifier and")).strip("_"), int(v), "int", "reports/eda/feature_catalog.csv", "count of columns in group")
    F.add("n_groups", len(groups), "int", "reports/eda/feature_catalog.csv", "number of feature groups")

    # ------------------------------------------------------------ missingness
    miss_pct = df.isna().mean() * 100
    per_row = df.isna().sum(axis=1)
    feat_cols = [c for c in cols if c not in ("SK_ID_CURR", "TARGET")]
    assert df[["SK_ID_CURR", "TARGET"]].isna().sum().sum() == 0, "ID and TARGET must never be empty"
    cells_missing, cells_total = int(df[feat_cols].isna().sum().sum()), int(df[feat_cols].size)
    F.add("n_feature_cols", len(feat_cols), "int", TR, "columns excluding the loan ID and TARGET")
    F.add("missing_cells", cells_missing, "int", TR, "empty cells across the feature columns")
    F.add("feature_cells_total", cells_total, "int", TR, "rows times feature columns (ID and TARGET excluded, they are never empty)")
    F.add("feature_missing_cell_pct", cells_missing / cells_total * 100, "p2", TR, "empty cells divided by all feature cells")
    F.add("thr_missing_pct", 5, "p0", "site copy", "threshold used in the missing-data section (5% missing)")
    F.add("thr_const_pct", 99, "p0", "site copy", "threshold used for near-constant columns (99% one value)")
    F.add("n_cols_any_missing", int((miss_pct > 0).sum()), "int", TR, "columns with at least one missing value")
    F.add("n_cols_gt5", int((miss_pct > 5).sum()), "int", TR, "columns above 5% missing")
    F.add("n_cols_gt50", int((miss_pct > 50).sum()), "int", TR, "columns above 50% missing")
    F.add("n_cols_no_missing", int((miss_pct == 0).sum()), "int", TR, "columns with no missing value")
    F.add("complete_rows_pct", (per_row == 0).mean() * 100, "p2", TR, "rows with no missing value")
    F.add("median_missing_fields", per_row.median(), "int", TR, "median missing fields per row")
    clusters = mask_clusters(df)
    big = [cl for cl in clusters if miss_pct[cl[0]] > 5]
    F.add("n_patterns", len(clusters), "int", TR, "distinct missing patterns (identical masks)")
    F.add("n_patterns_gt5", len(big), "int", TR, "patterns above 5% missing")
    bld_idx = [i for i, cl in enumerate(big) if column_group(cl[0]) == "Building / housing attributes"]
    F.add("n_building_patterns", len(bld_idx), "int", TR, "building patterns above 5% missing")
    phi = phi_matrix(df, big)
    pb = phi.to_numpy()[np.ix_(bld_idx, bld_idx)]
    off = pb[np.triu_indices_from(pb, 1)]
    F.add("phi_building_min", off.min(), "f2", TR, "lowest phi between two building patterns")
    F.add("phi_building_max", off.max(), "f2", TR, "highest phi between two building patterns")
    car, occ = df["FLAG_OWN_CAR"], df["NAME_INCOME_TYPE"] == "Pensioner"
    F.add("own_car_age_missing_nonowner_pct", df.loc[car == "N", "OWN_CAR_AGE"].isna().mean() * 100, "p2", TR, "OWN_CAR_AGE missing where FLAG_OWN_CAR = N")
    F.add("occupation_missing_pensioner_pct", df.loc[occ, "OCCUPATION_TYPE"].isna().mean() * 100, "p2", TR, "OCCUPATION_TYPE missing among pensioners")
    F.add("n_pensioner", int(occ.sum()), "int", TR, "pensioner rows")
    bur = df["AMT_REQ_CREDIT_BUREAU_YEAR"].isna()
    F.add("bureau_block_missing_n", int(bur.sum()), "int", TR, "rows where the bureau block is missing")
    F.add("ext3_missing_given_bureau_pct", df.loc[bur, "EXT_SOURCE_3"].isna().mean() * 100, "p2", TR, "EXT_SOURCE_3 missing when bureau block missing")
    age_q = pd.qcut(-df["DAYS_BIRTH"] / 365.25, 5)
    es1_age = df["EXT_SOURCE_1"].isna().groupby(age_q, observed=True).mean() * 100
    F.add("ext1_missing_youngest_pct", es1_age.iloc[0], "p1", TR, "EXT_SOURCE_1 missing in the youngest age quintile")
    F.add("ext1_missing_oldest_pct", es1_age.iloc[-1], "p1", TR, "EXT_SOURCE_1 missing in the oldest age quintile")

    # families for the dumbbell chart
    first = mfeat[mfeat["cluster"].notna() & mfeat["rate_missing_pct"].notna()].drop_duplicates("cluster")
    bfam = first[first["group"] == "Building / housing attributes"]

    def fam(name, row):
        return {"family": name, "missing_pct": float(row["missing_pct"]), "rate_missing": float(row["rate_missing_pct"]),
                "rate_present": float(row["rate_present_pct"]), "gap_pp": float(row["gap_pp"])}

    def row_of(c):
        return mfeat[mfeat["column"] == c].iloc[0]

    families = [
        {"family": "Building attributes (19 patterns, median)", "missing_pct": float(bfam["missing_pct"].median()),
         "rate_missing": float(bfam["rate_missing_pct"].median()), "rate_present": float(bfam["rate_present_pct"].median()),
         "gap_pp": float(bfam["gap_pp"].median()), "range_missing": [float(bfam["rate_missing_pct"].min()), float(bfam["rate_missing_pct"].max())]},
        fam("Credit bureau enquiries (6 columns)", row_of("AMT_REQ_CREDIT_BUREAU_YEAR")),
        fam("EXT_SOURCE_3", row_of("EXT_SOURCE_3")), fam("EXT_SOURCE_1", row_of("EXT_SOURCE_1")),
        fam("OWN_CAR_AGE (no car)", row_of("OWN_CAR_AGE")), fam("OCCUPATION_TYPE (pensioners)", row_of("OCCUPATION_TYPE")),
    ]
    pos_gaps = [f["gap_pp"] for f in families if f["gap_pp"] > 0]
    allgaps = first["gap_pp"]
    F.add("gap_min_pp", allgaps[allgaps > 0].min(), "f2", "reports/eda/missingness_by_feature.csv", "smallest positive default-rate gap, missing minus present")
    F.add("gap_max_pp", allgaps.max(), "f2", "reports/eda/missingness_by_feature.csv", "largest default-rate gap")
    F.add("gap_occupation_pp", row_of("OCCUPATION_TYPE")["gap_pp"], "f2", "reports/eda/missingness_by_feature.csv", "occupation gap (negative)")
    F.add("n_patterns_positive_gap", int((allgaps > 0).sum()), "int", "reports/eda/missingness_by_feature.csv", "patterns above 5% with a higher default rate when missing")
    F.add("n_families_positive", len(pos_gaps), "int", "reports/eda/missingness_by_feature.csv", "families (of 6 shown) with a positive gap")
    F.add("n_families", len(families), "int", "reports/eda/missingness_by_feature.csv", "families shown in the chart")

    # ------------------------------------------------------------ signal
    def decile_ends(f):
        t = bins[(bins["feature"] == f) & (bins["bin"] != "missing")]
        return float(t["rate_pct"].iloc[0]), float(t["rate_pct"].iloc[-1]), int(t["n"].min()), int(t["n"].max())

    rk = ranking.set_index("feature")
    for f in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"):
        lo, hi, nmin, nmax = decile_ends(f)
        k = f.lower()
        F.add(f"{k}_dec_first", lo, "p2", "reports/eda/bivariate_numeric_bins.csv", "default rate in the lowest-value decile")
        F.add(f"{k}_dec_last", hi, "p2", "reports/eda/bivariate_numeric_bins.csv", "default rate in the highest-value decile")
        F.add(f"{k}_range_pp", rk.loc[f, "range_pp"], "f2", "reports/eda/bivariate_signal_ranking.csv", "highest minus lowest decile default rate")
        F.add(f"{k}_pearson", corr_t.set_index("feature").loc[f, "pearson"], "f4", "reports/eda/correlation_with_target.csv", "Pearson r with TARGET")
        F.add(f"{k}_missing_pct", miss_pct[f], "p2", TR, "share missing")
    F.add("ext_range_min_pp", min(rk.loc[f, "range_pp"] for f in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3")), "f2", "reports/eda/bivariate_signal_ranking.csv", "smallest of the three EXT ranges")
    F.add("ext_range_max_pp", max(rk.loc[f, "range_pp"] for f in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3")), "f2", "reports/eda/bivariate_signal_ranking.csv", "largest of the three EXT ranges")
    for f, k in (("AMT_GOODS_PRICE", "goods"), ("DAYS_EMPLOYED", "dayemp"), ("DAYS_BIRTH", "birth")):
        F.add(f"{k}_range_pp", rk.loc[f, "range_pp"], "f2", "reports/eda/bivariate_signal_ranking.csv", "decile default-rate range")
    F.add("days_birth_pearson", corr_t.set_index("feature").loc["DAYS_BIRTH", "pearson"], "s3", "reports/eda/correlation_with_target.csv", "Pearson r with TARGET")
    F.add("n_numeric_corr", len(corr_t), "int", "reports/eda/correlation_with_target.csv", "numeric columns in the correlation table")
    F.add("corr_threshold", 0.10, "f2", "site copy", "correlation threshold used on the page")
    F.add("n_corr_gt010", int((corr_t["abs_best"] > 0.10).sum()), "int", "reports/eda/correlation_with_target.csv", "numeric features with abs(Pearson) or abs(Spearman) above 0.10")
    F.add("n_corr_gt010_pearson", int((corr_t["pearson"].abs() > 0.10).sum()), "int", "reports/eda/correlation_with_target.csv", "numeric features with abs(Pearson) above 0.10")
    F.add("n_corr_gt010_spearman", int((corr_t["spearman"].abs() > 0.10).sum()), "int", "reports/eda/correlation_with_target.csv", "numeric features with abs(Spearman) above 0.10")
    F.add("n_ranked", len(ranking), "int", "reports/eda/bivariate_signal_ranking.csv", "numeric columns in the decile ranking")
    F.add("n_noise", int((ranking["range_over_null"] < 2).sum()), "int", "reports/eda/bivariate_signal_ranking.csv", "columns with range under 2x the shuffled-label range")
    F.add("n_per_decile_full", n // 10, "int", TR, "rows per decile for a fully observed column")
    t_ann = bins[(bins["feature"] == "AMT_ANNUITY") & (bins["bin"] != "missing")]["rate_pct"]
    F.add("annuity_dec_first", t_ann.iloc[0], "p2", "reports/eda/bivariate_numeric_bins.csv", "annuity lowest decile default rate")
    F.add("annuity_dec_peak", t_ann.max(), "p2", "reports/eda/bivariate_numeric_bins.csv", "annuity peak decile default rate")
    F.add("annuity_dec_last", t_ann.iloc[-1], "p2", "reports/eda/bivariate_numeric_bins.csv", "annuity highest decile default rate")
    F.add("annuity_spearman", rk.loc["AMT_ANNUITY", "spearman_with_target"], "s3", "reports/eda/bivariate_signal_ranking.csv", "Spearman with TARGET")

    # ------------------------------------------------------------ quirks
    de = df["DAYS_EMPLOYED"]
    sent = de == DAYS_EMPLOYED_SENTINEL
    F.add("sentinel_value", DAYS_EMPLOYED_SENTINEL, "raw", "src/data/eda.py", "placeholder constant")
    F.add("sentinel_n", int(sent.sum()), "int", TR, "rows with the placeholder")
    F.add("sentinel_pct", sent.mean() * 100, "p2", TR, "share of rows with the placeholder")
    F.add("sentinel_rate_pct", y[sent.to_numpy()].mean() * 100, "p2", TR, "default rate of placeholder rows")
    F.add("nonsentinel_rate_pct", y[~sent.to_numpy()].mean() * 100, "p2", TR, "default rate of other rows")
    inc_type = df["NAME_INCOME_TYPE"]
    F.add("sentinel_pensioner_n", int(inc_type[sent].eq("Pensioner").sum()), "int", TR, "placeholder rows that are pensioners")
    F.add("sentinel_unemployed_n", int(inc_type[sent].eq("Unemployed").sum()), "int", TR, "placeholder rows that are unemployed")
    F.add("sentinel_xna_org_n", int(((df["ORGANIZATION_TYPE"] == "XNA") & sent).sum()), "int", TR, "placeholder rows whose organisation type is XNA")
    inc = df["AMT_INCOME_TOTAL"]
    F.add("income_max", inc.max(), "int", TR, "largest income value")
    F.add("income_median", inc.median(), "int", TR, "median income")
    F.add("income_p99", inc.quantile(0.99), "int", TR, "99th percentile income")
    F.add("income_gt1m_n", int((inc > 1e6).sum()), "int", TR, "rows with income above 1,000,000")
    F.add("obs30_max", df["OBS_30_CNT_SOCIAL_CIRCLE"].max(), "int", TR, "largest OBS_30 count")
    F.add("obs30_p99", df["OBS_30_CNT_SOCIAL_CIRCLE"].quantile(0.99), "int", TR, "p99 OBS_30 count")
    F.add("children_max", df["CNT_CHILDREN"].max(), "int", TR, "largest children count")
    shares = {c: top_share_of(df[c]) for c in cols if c != "SK_ID_CURR"}
    F.add("n_near_constant", sum(v >= 0.99 for v in shares.values()), "int", TR, "columns with a top value of 99% or more")
    stems = sorted({c.rsplit("_", 1)[0] for c in cols if c.endswith("_AVG")})
    mins = []
    for st in stems:
        vv = [f"{st}_AVG", f"{st}_MEDI", f"{st}_MODE"]
        cm = df[vv].corr().to_numpy()
        mins.append(cm[np.triu_indices_from(cm, 1)].min())
    F.add("n_building_stems", len(stems), "int", TR, "building stems with AVG, MEDI and MODE versions")
    F.add("building_twin_corr_min", min(mins), "f3", TR, "lowest correlation among versions of one stem")
    ca = df["OWN_CAR_AGE"]
    vc_hi = ca[ca >= 60].value_counts()
    F.add("car_spike_n", int(ca.isin([64, 65]).sum()), "int", TR, "rows with car age 64 or 65")
    spike_ages = sorted(int(a) for a, c in ca[ca >= 60].value_counts().items() if c >= 100)
    F.add("car_spike_age_low", spike_ages[0], "int", TR, "lowest car age in the spike")
    F.add("car_spike_age_high", spike_ages[-1], "int", TR, "highest car age in the spike")
    F.add("car_gap_start", spike_ages[-1] + 1, "int", TR, "first car age after the spike")
    F.add("car_age_63_n", int((ca == 63).sum()), "int", TR, "rows with car age 63")
    F.add("car_next_largest_n", int(ca[ca < 60].value_counts().max()), "int", TR, "largest single car-age count below 60")
    F.add("car_age_max_gap", int(ca[ca > 65].max()), "int", TR, "largest car age above 65")
    gp = df["AMT_GOODS_PRICE"]
    top_val = gp.value_counts().index[0]
    mk = gp == top_val
    F.add("goods_clump_value", top_val, "int", TR, "most common goods price")
    F.add("goods_clump_n", int(mk.sum()), "int", TR, "rows at that goods price")
    F.add("goods_clump_pct", mk.mean() * 100, "p2", TR, "share of rows at that goods price")
    F.add("goods_clump_rate_pct", y[mk.to_numpy()].mean() * 100, "p2", TR, "default rate at that goods price")
    F.add("goods_other_rate_pct", y[~mk.to_numpy()].mean() * 100, "p2", TR, "default rate elsewhere")
    F.add("goods_clump_cash_pct", (df.loc[mk, "NAME_CONTRACT_TYPE"] == "Cash loans").mean() * 100, "p1", TR, "cash loans among clump rows")
    F.add("n_rare_categories", int(catsum["rare"].sum()), "int", "reports/eda/categorical_summary.csv", "category rows under 1% of rows")
    F.add("n_category_rows", len(catsum), "int", "reports/eda/categorical_summary.csv", "category rows in text columns")
    F.add("n_text_cols", int(catsum["column"].nunique()), "int", "reports/eda/categorical_summary.csv", "text columns")
    F.add("n_xna_gender", int((df["CODE_GENDER"] == "XNA").sum()), "int", TR, "gender XNA rows")

    # ------------------------------------------------------------ shortlist
    st = shortlist["status"].value_counts()
    core = shortlist[shortlist["status"] == "shortlist"]["feature"].tolist()
    pend = shortlist[shortlist["status"] == "shortlist (needs ruling)"]["feature"].tolist()
    chosen = core + pend
    SL = "reports/eda/feature_shortlist.csv"
    F.add("n_shortlist", len(chosen), "int", SL, "shortlisted columns")
    F.add("n_core", len(core), "int", SL, "core picks")
    F.add("n_pending", len(pend), "int", SL, "picks that need a ruling")
    F.add("n_options", int(st.get("excluded (option, needs ruling)", 0)), "int", SL, "excluded options")
    F.add("n_excluded", int(st.get("excluded", 0)), "int", SL, "excluded columns")
    ex = shortlist[shortlist["status"] == "excluded"]
    F.add("n_ex_building", int(ex["reason"].str.startswith("Building block").sum()), "int", SL, "excluded building columns")
    F.add("n_ex_docs", int(ex["feature"].str.startswith("FLAG_DOCUMENT_").sum()), "int", SL, "excluded document flags")
    F.add("shortlist_min", 25, "int", "README.md", "README range for the shortlist", "DOC")
    F.add("shortlist_max", 40, "int", "README.md", "README range for the shortlist", "DOC")
    numcols = [c for c in chosen if df[c].dtype != object]
    cl = pd.DataFrame({c: (df[c].where(df[c] != DAYS_EMPLOYED_SENTINEL) if c == "DAYS_EMPLOYED" else df[c]) for c in numcols}).corr()
    iu = np.triu_indices_from(cl.to_numpy(), 1)
    F.add("shortlist_max_corr", np.abs(cl.to_numpy()[iu]).max(), "f2", TR, "largest abs Pearson r between two shortlisted numeric columns")
    F.add("shortlist_fully_observed", int((df[chosen].isna().sum() == 0).sum()), "int", TR, "shortlisted columns with no missing value")
    F.add("shortlist_missing_gt5", int((df[chosen].isna().mean() * 100 > 5).sum()), "int", TR, "shortlisted columns above 5% missing")

    # ------------------------------------------------------------ candidate clean-state numbers
    e1, e2, e3 = df["EXT_SOURCE_1"], df["EXT_SOURCE_2"], df["EXT_SOURCE_3"]
    F.add("ext2_corr_ext1", e2.corr(e1), "f3", TR, "Pearson r EXT_SOURCE_2 vs EXT_SOURCE_1")
    F.add("ext2_corr_ext3", e2.corr(e3), "f3", TR, "Pearson r EXT_SOURCE_2 vs EXT_SOURCE_3")
    F.add("ext_all_present_pct", df[["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]].notna().all(axis=1).mean() * 100, "p2", TR, "rows with all three scores")
    F.add("income_range_pp", rk.loc["AMT_INCOME_TOTAL", "range_pp"], "f2", "reports/eda/bivariate_signal_ranking.csv", "income decile default-rate range")
    F.add("income_spearman", rk.loc["AMT_INCOME_TOTAL", "spearman_with_target"], "s3", "reports/eda/bivariate_signal_ranking.csv", "Spearman with TARGET")
    an = df["AMT_ANNUITY"]
    term = (df["AMT_CREDIT"] / an).dropna()
    F.add("term_p10", term.quantile(0.1), "f1", TR, "implied term p10 (AMT_CREDIT / AMT_ANNUITY)")
    F.add("term_p50", term.quantile(0.5), "f1", TR, "implied term median")
    F.add("term_p90", term.quantile(0.9), "f1", TR, "implied term p90")
    F.add("credit_median", df["AMT_CREDIT"].median(), "int", TR, "median AMT_CREDIT")
    F.add("annuity_median", an.median(), "int", TR, "median AMT_ANNUITY")
    last = bins[(bins["feature"] == "DAYS_EMPLOYED") & (bins["bin"] != "missing")].iloc[-1]
    F.add("shortest_tenure_rate_pct", last["rate_pct"], "p2", "reports/eda/bivariate_numeric_bins.csv", "default rate in the shortest-tenure decile")
    F.add("shortest_tenure_n", int(last["n"]), "int", "reports/eda/bivariate_numeric_bins.csv", "rows in that decile")
    F.add("half_placeholder_share_pct", sent.sum() * 0.5 / n * 100, "p0", TR, "half of the placeholder rows as a share of all rows")

    # AI-drafted prediction numbers: entered by hand, verified to appear in the draft file
    DR = "reports/eda/section8_corruption_candidates.md (AI draft)"
    for key, text in {"pred_ext2_low": "0.01", "pred_ext2_high": "0.03", "pred_income_max": "0.005", "pred_amount_low": "0.005",
                      "pred_amount_high": "0.02", "pred_dayemp_max": "0.01", "pred_brandom_max": "0.01", "pred_clean_low": "+0.01",
                      "pred_clean_high": "+0.03"}.items():
        F.add(key, text, "raw", DR, "typed by hand from the AI draft, checked to appear in it", "DRAFT", verify_in=cand_md)

    # ------------------------------------------------------------ registry for the copy check
    reg = set(num_tokens(eda_blob))
    for col in ("notes", "official_description", "value_summary"):
        for s_ in cat[col].dropna():
            reg |= num_tokens(str(s_))
    for s_ in shortlist["reason"].dropna():
        reg |= num_tokens(str(s_))
    for item in F.items.values():
        reg |= num_tokens(item["text"])

    # ------------------------------------------------------------ per-feature records
    quirk_text = build_quirks(F)
    sl = shortlist.set_index("feature")
    cats_by_col = {c: g for c, g in catsum.groupby("column")}
    flag_rows = flags.set_index("feature")
    features = []
    for _, r in cat.iterrows():
        name = r["name"]
        s = df[name]
        stype = r["semantic_type"]
        rec = {"name": name, "group": r["group"], "description": ascii_clean(r["official_description"]), "dtype": r["dtype"], "type": stype,
               "missing_pct": float(r["missing_pct"]), "n_unique": int(r["n_unique"]),
               "shortlist": STATUS_MAP[sl.loc[name, "status"]], "shortlist_reason": sl.loc[name, "reason"],
               "sensitive": name in SENSITIVE, "candidate": name in CANDIDATE_FEATURES, "notes": "" if pd.isna(r["notes"]) else r["notes"],
               "quirks": quirk_text.get(name, []), "dist": distribution(name, s, stype)}
        if name == "SK_ID_CURR":
            rec["dist"] = {"kind": "none"}
        rb = []
        if name in cats_by_col:
            for c in cats_by_col[name].sort_values("n", ascending=False).itertuples():
                rb.append({"label": c.category, "n": int(c.n), "rate": None if c.n < MIN_CELL else round(c.rate_pct, 2),
                           "lo": None if c.n < MIN_CELL else round(c.ci_lo_pct, 2), "hi": None if c.n < MIN_CELL else round(c.ci_hi_pct, 2)})
        elif name in flag_rows.index:
            f_ = flag_rows.loc[name]
            for lab, nn, rr in (("0", f_["n_0"], f_["rate_when_0_pct"]), ("1", f_["n_1"], f_["rate_when_1_pct"])):
                rb.append({"label": lab, "n": int(nn), "rate": None if nn < MIN_CELL else round(float(rr), 2), "lo": None, "hi": None})
        else:
            for c in bins[bins["feature"] == name].itertuples():
                rb.append({"label": c.bin, "n": int(c.n), "rate": None if c.n < MIN_CELL else round(c.rate_pct, 2),
                           "lo": None if c.n < MIN_CELL else round(c.ci_lo_pct, 2), "hi": None if c.n < MIN_CELL else round(c.ci_hi_pct, 2)})
        rec["rate_bins"] = rb
        if name in rk.index:
            rec["range_pp"] = round(float(rk.loc[name, "range_pp"]), 2)
            rec["null_range_pp"] = round(float(rk.loc[name, "null_range_pp"]), 2)
            rec["spearman"] = round(float(rk.loc[name, "spearman_with_target"]), 3)
        features.append(rec)
    assert len(features) == len(cols)

    # ------------------------------------------------------------ charts
    top = ranking.sort_values("range_pp", ascending=False).head(12)
    patterns = []
    for i, cl_ in enumerate(big):
        row = mfeat[mfeat["column"] == cl_[0]].iloc[0]
        patterns.append({"label": cluster_label(cl_), "n_cols": len(cl_), "group": column_group(cl_[0]),
                         "missing_pct": round(float(row["missing_pct"]), 2), "rate_missing": round(float(row["rate_missing_pct"]), 2),
                         "rate_present": round(float(row["rate_present_pct"]), 2), "gap_pp": round(float(row["gap_pp"]), 2)})
    sl_matrix = [{"name": r.feature, "group": r.group, "status": STATUS_MAP[r.status], "reason": r.reason} for r in shortlist.itertuples()]
    de_rec = next(f for f in features if f["name"] == "DAYS_EMPLOYED")
    edges_y = [-e / 365.25 for e in de_rec["dist"]["edges"]]
    charts = {
        "groups": [{"group": g, "n": int(v)} for g, v in groups.items()],
        "types": [{"type": k, "n": int(v)} for k, v in types.items()],
        "waffle": {"filled": int(round(npos / n * 100)), "of": 100},
        "missing_by_group": [{"group": r.group, "columns": int(r.columns), "mean_missing_pct": float(r.mean_missing_pct_all_cols),
                              "with_missing": int(r.columns_with_missing)} for r in mgroup.itertuples()],
        "dumbbell": families,
        "patterns": patterns,
        "heatmap": {"labels": [cluster_label(cl_) for cl_ in big], "groups": [column_group(cl_[0]) for cl_ in big],
                    "phi": [[round(float(v), 2) for v in row] for row in phi.to_numpy()]},
        "signal_top": [{"feature": r.feature, "group": r.group, "range_pp": round(r.range_pp, 2), "null_range_pp": round(r.null_range_pp, 2),
                        "spearman": round(r.spearman_with_target, 3)} for r in top.itertuples()],
        "days_employed_hist": {"edges_years": [round(float(e), 3) for e in sorted(edges_y)], "counts": de_rec["dist"]["counts"][::-1],
                               "placeholder_n": de_rec["dist"]["n_placeholder"], "below": de_rec["dist"]["above"], "above": de_rec["dist"]["below"]},
        "shortlist_matrix": sl_matrix,
        "exclusion_reasons": [{"reason": r_, "n": int(c)} for r_, c in ex["reason"].value_counts().items()],
        "candidates": build_candidates(F),
        "roadmap": ROADMAP,
    }

    # ------------------------------------------------------------ content (text imported from the repo)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    hyp = re.search(r"## Hypothesis\s+(.*?)\n## ", readme, re.S).group(1).strip()
    decided = re.search(r"\*\*Decided:\*\* (\d{4}-\d{2}-\d{2})", (ROOT / "docs/decisions/0.1-hypothesis-statement.md").read_text(encoding="utf-8")).group(1)
    content = {"hypothesis": {"text": hyp, "decided": decided, "source": "README.md, Hypothesis section; docs/decisions/0.1-hypothesis-statement.md"}}
    reg |= num_tokens(hyp) | num_tokens(decided)

    facts_out = {"facts": F.items, "registry": sorted(reg), "meta": {"train_rows": n, "script": "site/build_data.py", "min_cell": MIN_CELL}}
    for fname, obj in (("facts.json", facts_out), ("features.json", features), ("charts.json", charts), ("content.json", content)):
        (DATA_DIR / fname).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    write_facts_table(F, features, charts)
    print(f"facts: {len(F.items)}, registry numbers: {len(reg)}, features: {len(features)}")
    for fn in sorted(DATA_DIR.glob("*.json")):
        print(f"  {fn.name}: {fn.stat().st_size / 1024:.0f} KB")


def top_share_of(s: pd.Series) -> float:
    vc = s.value_counts(dropna=True)
    return float(vc.iloc[0] / vc.sum())


ROADMAP = [
    {"phase": 1, "title": "Data acquisition and EDA", "state": "done"},
    {"phase": 2, "title": "WOE and IV feature engineering", "state": "next"},
    {"phase": 3, "title": "Data quality corruption simulator", "state": "later"},
    {"phase": 4, "title": "Three-tier modelling", "state": "later"},
    {"phase": 5, "title": "Evaluation on the untouched holdout", "state": "later"},
    {"phase": 6, "title": "Explainability (SHAP)", "state": "later"},
    {"phase": 7, "title": "Results: expected versus actual", "state": "later"},
    {"phase": 8, "title": "Not yet scoped", "state": "later"},
    {"phase": 9, "title": "Write-up and article", "state": "later"},
]


def build_quirks(F: Facts) -> dict[str, list[dict]]:
    t = F.t
    q: dict[str, list[dict]] = {}

    def add(name, tag, text):
        q.setdefault(name, []).append({"tag": tag, "text": text})

    add("DAYS_EMPLOYED", "DATA", f"The value {t('sentinel_value')} appears in {t('sentinel_n')} rows ({t('sentinel_pct')}). They are {t('sentinel_pensioner_n')} pensioners and {t('sentinel_unemployed_n')} unemployed. Default rate {t('sentinel_rate_pct')} against {t('nonsentinel_rate_pct')} for other rows.")
    add("ORGANIZATION_TYPE", "DATA", f"XNA appears in {t('sentinel_xna_org_n')} rows, the same rows as the DAYS_EMPLOYED placeholder.")
    add("AMT_INCOME_TOTAL", "DATA", f"Largest value {t('income_max')} against a median of {t('income_median')} and a 99th percentile of {t('income_p99')}.")
    add("OWN_CAR_AGE", "DATA", f"{t('car_spike_n')} rows have an age of 64 or 65, one row has 63, and nothing lies between 66 and 90. Cause not verified.")
    add("AMT_GOODS_PRICE", "DATA", f"{t('goods_clump_pct')} of rows equal {t('goods_clump_value')}, with a default rate of {t('goods_clump_rate_pct')} against {t('goods_other_rate_pct')} elsewhere. Cause not verified.")
    add("OBS_30_CNT_SOCIAL_CIRCLE", "DATA", f"Largest value {t('obs30_max')} against a 99th percentile of {t('obs30_p99')}.")
    add("CNT_CHILDREN", "DATA", f"Largest value {t('children_max')}.")
    add("EXT_SOURCE_1", "DATA", f"Missing share rises with age, from {t('ext1_missing_youngest_pct')} in the youngest quintile to {t('ext1_missing_oldest_pct')} in the oldest.")
    add("EXT_SOURCE_3", "DATA", f"When the credit bureau enquiry block is missing, this score is missing in {t('ext3_missing_given_bureau_pct')} of those rows.")
    add("AMT_ANNUITY", "DATA", f"Spearman with TARGET is {t('annuity_spearman')}, yet decile default rates run from {t('annuity_dec_first')} up to {t('annuity_dec_peak')} and down to {t('annuity_dec_last')}.")
    add("OCCUPATION_TYPE", "DATA", f"Missing for {t('occupation_missing_pensioner_pct')} of pensioners. This is structural.")
    add("FLAG_OWN_CAR", "DATA", f"OWN_CAR_AGE is missing for {t('own_car_age_missing_nonowner_pct')} of non-owners.")
    for f in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"):
        add(f, "HYPOTHESIS", "The source and timing of this score are not documented. If it holds information from after the loan was granted, results would be inflated. Not verified.")
    for f in ("OBS_30_CNT_SOCIAL_CIRCLE", "OBS_60_CNT_SOCIAL_CIRCLE", "DEF_30_CNT_SOCIAL_CIRCLE", "DEF_60_CNT_SOCIAL_CIRCLE"):
        add(f, "HYPOTHESIS", "When these counts were observed relative to the loan is not documented, so they could carry outcome information. Not verified.")
    for f in ("CODE_GENDER", "DAYS_BIRTH", "NAME_FAMILY_STATUS", "CNT_CHILDREN", "CNT_FAM_MEMBERS"):
        add(f, "NOTE", "Sensitive attribute. Shown here as a descriptive column only. This project does not use it to make decisions about people, and fairness is out of scope for this phase.")
    add("CODE_GENDER", "DATA", f"{t('n_xna_gender')} rows are coded XNA.")
    return q


def build_candidates(F: Facts) -> list[dict]:
    t = F.t
    return [
        {"slug": "ext2", "target": "EXT_SOURCE_2", "scenario": "A", "scenario_name": "MNAR missingness", "rank": 1,
         "failure": "The outside bureau does not return a score for applicants it cannot score.",
         "clean": f"{t('ext_source_2_missing_pct')} missing. Decile default rate runs from {t('ext_source_2_dec_first')} to {t('ext_source_2_dec_last')}. Correlation with the other two scores is only {t('ext2_corr_ext1')} and {t('ext2_corr_ext3')}.",
         "prediction": f"Both models lose AUC at every step. At 50% severity the drop is about {t('pred_ext2_low')} to {t('pred_ext2_high')}. The premium stays above zero.",
         "falsifier": "The premium interval includes zero at 25% or less, or the scorecard loses less than the GBM.", "confidence": "medium-low"},
        {"slug": "income", "target": "AMT_INCOME_TOTAL", "scenario": "A", "scenario_name": "MNAR missingness", "rank": 5,
         "failure": "Self-reported income is left blank, and who leaves it blank depends on the amount.",
         "clean": f"Fully observed. Weak alone: Spearman {t('income_spearman')}, decile range {t('income_range_pp')} points.",
         "prediction": f"At 50% severity the drop is {t('pred_income_max')} or less for both models. The premium is unchanged.",
         "falsifier": "A drop above 0.01, which would mean income matters through its link to the loan amounts.", "confidence": "low-medium"},
        {"slug": "labels", "target": "TARGET (training labels)", "scenario": "B", "scenario_name": "Label lag", "rank": 2,
         "failure": "Late defaults are not yet recorded when the training set is cut, and long loans are hit hardest.",
         "clean": f"{t('n_pos')} defaults ({t('default_rate_pct')}). Hiding 50% of them would leave a default rate of {t('hide_50_rate_pct')}.",
         "prediction": f"Hiding defaults at random is mild, at most {t('pred_brandom_max')}. Hiding that depends on loan term hurts the GBM more, and the premium interval may include zero at 25% to 50%.",
         "falsifier": "Random hiding hurts more than term-based hiding, or the premium stays clearly above zero at 50%.", "confidence": "low-medium"},
        {"slug": "amounts", "target": "AMT_CREDIT and AMT_ANNUITY", "scenario": "C", "scenario_name": "Scale drift", "rank": 3,
         "failure": "Amount fields change units or are re-based between systems.",
         "clean": f"Median credit {t('credit_median')}, median annuity {t('annuity_median')}. Both are hump-shaped against default.",
         "prediction": f"The drop is {t('pred_amount_low')} to {t('pred_amount_high')} for both models, with no clear difference between them. The premium is unchanged.",
         "falsifier": "The GBM drop is clearly larger than the scorecard drop.", "confidence": "low"},
        {"slug": "placeholder", "target": "DAYS_EMPLOYED placeholder", "scenario": "C", "scenario_name": "Schema drift", "rank": 4,
         "failure": "A source system re-encodes 'not employed'.",
         "clean": f"{t('sentinel_n')} rows ({t('sentinel_pct')}) hold the placeholder, with a {t('sentinel_rate_pct')} default rate. Recoded to 0 days, they would land in a group that defaults at {t('shortest_tenure_rate_pct')}. Severity must count placeholder rows only, so 50% of them is about {t('half_placeholder_share_pct')} of all rows.",
         "prediction": f"At 50% severity the drop is {t('pred_dayemp_max')} or less, because the income-type column partly offsets the error. The premium is unchanged.",
         "falsifier": "A drop above 0.02.", "confidence": "low"},
    ]


def write_facts_table(F: Facts, features: list, charts: dict) -> None:
    lines = ["# Site facts table (Gate 2, local review file)", "",
             "Every number the site copy can use. 'In EDA text' = the same figure already appears in a file in `reports/eda/`. 'new' = computed here for the site and not in the EDA text.", "",
             f"{len(F.items)} facts. DATA = computed or parsed from the train split or EDA outputs. DOC = from documentation. DRAFT = AI-drafted prediction number, verified against its source file.", "",
             "| Key | Shown as | Label | Source | How | In EDA text |", "|---|---|---|---|---|---|"]
    for k, v in F.items.items():
        lines.append(f"| `{k}` | {v['text']} | {v['label']} | {v['source']} | {v['how']} | {'yes' if v['in_eda_text'] else 'new'} |")
    new = [k for k, v in F.items.items() if not v["in_eda_text"]]
    lines += ["", f"New numbers (not found in the EDA text): {len(new)}", "", ", ".join(f"`{k}`" for k in new), ""]
    FACTS_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
