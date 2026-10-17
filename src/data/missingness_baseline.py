"""Missingness baseline (EDA session, Section 5).

Reads data/processed/train.csv ONLY. Writes to reports/eda/:
  missingness_by_feature.csv   per column: group, cluster, missing n/%, default rate gap (if > 5% missing)
  missingness_by_group.csv     per feature group
  section5_facts.md            the numbers behind the written notes
  figures/missingness_*.png    three charts

Numbers only. Whether a pattern is MCAR / MAR / MNAR is a hypothesis, written by
hand in section5_missingness.md. Nothing here injects missingness (that is Phase 3).

Terms used below:
  cluster   columns whose missing/not-missing pattern is identical row by row
  gap       default rate when missing minus default rate when present, in percentage points
  Cramer's V  strength of association between two categorical variables, 0 to 1
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import chi2_contingency  # noqa: E402

from src.data.eda import column_group, group_counts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
REPORT_DIR = ROOT / "reports" / "eda"
FIG_DIR = REPORT_DIR / "figures"

MISSING_MIN_PCT = 5.0  # only columns above this get a default-rate comparison
INFORMATIVE_MIN_PP = 1.0  # EDA convention, not a project rule: flag if |gap| >= 1 pp and the 95% CI excludes 0

# Fully observed covariates used to ask "does missingness depend on something we can see?"
CAT_COVARIATES = [
    "NAME_CONTRACT_TYPE", "CODE_GENDER", "FLAG_OWN_CAR", "FLAG_OWN_REALTY", "NAME_INCOME_TYPE",
    "NAME_EDUCATION_TYPE", "NAME_FAMILY_STATUS", "NAME_HOUSING_TYPE", "ORGANIZATION_TYPE",
    "REGION_RATING_CLIENT", "WEEKDAY_APPR_PROCESS_START",
]
NUM_COVARIATES = [
    "DAYS_BIRTH", "DAYS_EMPLOYED", "DAYS_REGISTRATION", "DAYS_ID_PUBLISH",
    "AMT_INCOME_TOTAL", "AMT_CREDIT", "REGION_POPULATION_RELATIVE",
]

INK, INK2, GRID, BLUE, GREY = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6", "#9a9992"


def mask_clusters(df: pd.DataFrame) -> list[list[str]]:
    """Columns with identical missing masks, clusters ordered by missing % (desc) then name. Pure."""
    miss = df.isna()
    by_key: dict[str, list[str]] = {}
    for c in df.columns:
        if miss[c].any():
            by_key.setdefault(hashlib.md5(miss[c].to_numpy().tobytes()).hexdigest(), []).append(c)
    clusters = [sorted(v) for v in by_key.values()]
    clusters.sort(key=lambda cols: (-miss[cols[0]].mean(), cols[0]))
    return clusters


def default_rate_gap(y: np.ndarray, missing: np.ndarray) -> dict:
    """Default rate when missing vs present, gap in percentage points with a Wald 95% CI. Pure."""
    n1, n0 = int(missing.sum()), int((~missing).sum())
    p1, p0 = float(y[missing].mean()), float(y[~missing].mean())
    gap = p1 - p0
    se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    lo, hi = gap - 1.96 * se, gap + 1.96 * se
    return {
        "n_missing": n1, "n_present": n0,
        "rate_missing_pct": p1 * 100, "rate_present_pct": p0 * 100,
        "gap_pp": gap * 100, "ci_lo_pp": lo * 100, "ci_hi_pp": hi * 100,
        "ratio": p1 / p0,
        "informative": bool(abs(gap) * 100 >= INFORMATIVE_MIN_PP and (lo > 0 or hi < 0)),
    }


def adjusted_gap(y: np.ndarray, missing: np.ndarray, strata: pd.Series, min_n: int = 30) -> tuple[float, float]:
    """Default-rate gap (pp) computed inside strata of observed variables, then averaged with
    stratum-size weights. Strata with fewer than min_n rows on either side are dropped.
    Returns (adjusted gap in pp, share of rows used). Pure."""
    d = pd.DataFrame({"y": y, "m": missing, "s": strata.to_numpy()})
    g = d.groupby(["s", "m"])["y"].agg(["size", "mean"]).unstack("m")
    if (("size", True) not in g.columns) or (("size", False) not in g.columns):
        return float("nan"), 0.0
    g = g.dropna()
    g = g[(g[("size", True)] >= min_n) & (g[("size", False)] >= min_n)]
    if g.empty:
        return float("nan"), 0.0
    w = g[("size", True)] + g[("size", False)]
    gap = (g[("mean", True)] - g[("mean", False)]) * 100
    return float((w * gap).sum() / w.sum()), float(w.sum() / len(d))


def cramers_v(a: pd.Series, b: pd.Series) -> float:
    """Cramer's V between two discrete series. Pure."""
    table = pd.crosstab(a, b)
    if min(table.shape) < 2:
        return float("nan")
    chi2 = chi2_contingency(table, correction=False)[0]
    return float(np.sqrt(chi2 / (table.to_numpy().sum() * (min(table.shape) - 1))))


def covariate_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Observed covariates as discrete series: categories as is, numerics in 5 quantile bins. Pure."""
    out = {c: df[c].astype(str) for c in CAT_COVARIATES}
    for c in NUM_COVARIATES:
        out[c] = pd.qcut(df[c], 5, duplicates="drop").astype(str)
    return pd.DataFrame(out)


def phi_matrix(df: pd.DataFrame, clusters: list[list[str]]) -> pd.DataFrame:
    """Pearson correlation of 0/1 missing indicators (phi), one row per cluster. Pure."""
    ind = pd.DataFrame({cl[0]: df[cl[0]].isna().astype(int) for cl in clusters})
    return ind.corr()


def cluster_label(cols: list[str]) -> str:
    return cols[0] if len(cols) == 1 else f"{cols[0]} (+{len(cols) - 1})"


def _style(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)


def plot_group_bar(grp: pd.DataFrame, path: Path) -> None:
    g = grp[grp["columns_with_missing"] > 0].sort_values("mean_missing_pct_all_cols")
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(g) + 1.4))
    ax.barh(g["group"], g["mean_missing_pct_all_cols"], color=BLUE, height=0.55)
    for y, (v, k, n) in enumerate(zip(g["mean_missing_pct_all_cols"], g["columns_with_missing"], g["columns"])):
        ax.text(v + 0.8, y, f"{v:.1f}%  ({k} of {n} columns have missing)", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Mean missing % across all columns in the group (train)", color=INK2, fontsize=9)
    ax.set_title("Missingness by feature group", loc="left", color=INK, fontsize=11)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_phi_heatmap(phi: pd.DataFrame, labels: list[str], path: Path) -> None:
    k = len(labels)
    fig, ax = plt.subplots(figsize=(0.32 * k + 4, 0.32 * k + 3))
    im = ax.imshow(phi.to_numpy(), cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
        "blue", ["#cde2fb", "#2a78d6", "#0d366b"]), vmin=0, vmax=1)
    ax.set_xticks(range(k), labels, rotation=90, fontsize=6.5, color=INK2)
    ax.set_yticks(range(k), labels, fontsize=6.5, color=INK2)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("phi (correlation of missing indicators)", fontsize=8, color=INK2)
    ax.set_title("Which missing patterns occur together (train)", loc="left", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_gap(gaps: pd.DataFrame, path: Path) -> None:
    g = gaps.sort_values("gap_pp").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 0.3 * len(g) + 1.6))
    ax.axvspan(-INFORMATIVE_MIN_PP, INFORMATIVE_MIN_PP, color=GRID, alpha=0.6, zorder=0)
    ax.axvline(0, color=INK2, linewidth=0.8)
    for i, r in g.iterrows():
        col = BLUE if r["informative"] else GREY
        ax.plot([r["ci_lo_pp"], r["ci_hi_pp"]], [i, i], color=col, linewidth=1.4)
        ax.plot(r["gap_pp"], i, "o", color=col, markersize=6, markeredgecolor="white", markeredgewidth=1)
    ax.set_yticks(range(len(g)), g["label"], fontsize=7.5, color=INK2)
    ax.set_xlabel("Default rate when missing minus when present (percentage points, 95% CI)", color=INK2, fontsize=9)
    ax.set_title("Is the fact that a value is missing related to default?  (blue = flagged)", loc="left", color=INK, fontsize=11)
    ax.text(0.99, 0.02, f"grey band: +/-{INFORMATIVE_MIN_PP:.0f} pp", transform=ax.transAxes, ha="right", fontsize=8, color=INK2)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(TRAIN_PATH)
    n = len(df)
    y = df["TARGET"].to_numpy()
    miss_pct = df.isna().mean() * 100
    clusters = mask_clusters(df)
    cluster_of = {c: i + 1 for i, cl in enumerate(clusters) for c in cl}

    # strata of observed variables used to ask whether a gap survives adjustment
    strata = df["NAME_INCOME_TYPE"].astype(str) + "|" + df["REGION_RATING_CLIENT"].astype(str)

    # ---- per feature ----
    rows = []
    for c in df.columns:
        k = int(df[c].isna().sum())
        row = {"column": c, "group": column_group(c), "cluster": f"M{cluster_of[c]:02d}" if c in cluster_of else "",
               "missing_n": k, "missing_pct": round(miss_pct[c], 3)}
        if miss_pct[c] > MISSING_MIN_PCT:
            row.update({k2: (round(v, 3) if isinstance(v, float) else v)
                        for k2, v in default_rate_gap(y, df[c].isna().to_numpy()).items()})
            adj, used = adjusted_gap(y, df[c].isna().to_numpy(), strata)
            row.update({"adjusted_gap_pp": round(adj, 3), "adjusted_rows_used_pct": round(used * 100, 1)})
        rows.append(row)
    feat = pd.DataFrame(rows).sort_values(["missing_pct", "column"], ascending=[False, True])
    feat.to_csv(REPORT_DIR / "missingness_by_feature.csv", index=False)

    # ---- per group ----
    gc = group_counts(list(df.columns))
    grows = []
    for g, cols in gc.items():
        sub = df[cols]
        grows.append({
            "group": g, "columns": len(cols),
            "columns_with_missing": int((sub.isna().sum() > 0).sum()),
            "columns_over_5pct": int((miss_pct[cols] > 5).sum()),
            "columns_over_50pct": int((miss_pct[cols] > 50).sum()),
            "mean_missing_pct_all_cols": round(float(miss_pct[cols].mean()), 2),
            "max_missing_pct": round(float(miss_pct[cols].max()), 2),
            "rows_with_any_missing_pct": round(float(sub.isna().any(axis=1).mean() * 100), 2),
        })
    grp = pd.DataFrame(grows)
    grp.to_csv(REPORT_DIR / "missingness_by_group.csv", index=False)
    plot_group_bar(grp, FIG_DIR / "missingness_by_group.png")

    # ---- clusters over 5% ----
    big = [cl for cl in clusters if miss_pct[cl[0]] > MISSING_MIN_PCT]
    gaps = []
    for cl in big:
        d = default_rate_gap(y, df[cl[0]].isna().to_numpy())
        adj, used = adjusted_gap(y, df[cl[0]].isna().to_numpy(), strata)
        d.update({"adj_gap_pp": adj, "adj_used": used})
        d.update({"cluster": f"M{cluster_of[cl[0]]:02d}", "label": cluster_label(cl), "n_cols": len(cl),
                  "missing_pct": miss_pct[cl[0]], "cols": cl})
        gaps.append(d)
    gaps = pd.DataFrame(gaps)
    plot_gap(gaps, FIG_DIR / "missingness_default_gap.png")

    phi = phi_matrix(df, big)
    plot_phi_heatmap(phi, [cluster_label(cl) for cl in big], FIG_DIR / "missingness_cluster_corr.png")

    # ---- MAR probe: which observed variable is the missing pattern most tied to ----
    cov = covariate_frame(df)
    probe = []
    for cl in big:
        m = df[cl[0]].isna().astype(int)
        v = {c: cramers_v(m, cov[c]) for c in cov.columns}
        top = sorted(v.items(), key=lambda kv: -kv[1])[:3]
        probe.append((cluster_label(cl), top))

    # ---- row level ----
    per_row = df.isna().sum(axis=1)
    bins = [-1, 0, 5, 20, 40, 60, 200]
    names = ["0", "1-5", "6-20", "21-40", "41-60", "61+"]
    bucket = pd.cut(per_row, bins=bins, labels=names)
    rowtab = df.groupby(bucket, observed=True)["TARGET"].agg(["size", "mean"])

    # ---- write facts ----
    out = ["# Section 5 facts (train split only)", "",
           "Generated by `src/data/missingness_baseline.py`. Numbers only. Interpretation is in `section5_missingness.md`.", ""]
    out += ["## Headline", "",
            f"- Columns with any missing: {int((miss_pct > 0).sum())} of {df.shape[1]}; over 5%: {int((miss_pct > 5).sum())}; over 50%: {int((miss_pct > 50).sum())}.",
            f"- Distinct missing patterns (clusters of identical masks) among the {int((miss_pct > 0).sum())} columns: {len(clusters)}. Over 5%: {len(big)} clusters covering {sum(len(c) for c in big)} columns.",
            f"- Rows with zero missing values across all 122 columns: {int((per_row == 0).sum()):,} ({(per_row == 0).mean():.2%}). Median missing fields per row: {per_row.median():.0f}; max {per_row.max()}.", ""]
    out += ["## Missing % per feature (top 25; full list in `missingness_by_feature.csv`)", "", "| Column | Group | Missing n | Missing % |", "|---|---|---|---|"]
    out += [f"| {r.column} | {r.group} | {r.missing_n:,} | {r.missing_pct:.2f} |" for r in feat.head(25).itertuples()]
    out += ["", "## Missing % by feature group", "", "| Group | Columns | With missing | Over 5% | Over 50% | Mean missing % | Max % | Rows with any missing in group |", "|---|---|---|---|---|---|---|---|"]
    out += [f"| {r.group} | {r.columns} | {r.columns_with_missing} | {r.columns_over_5pct} | {r.columns_over_50pct} | {r.mean_missing_pct_all_cols:.2f} | {r.max_missing_pct:.2f} | {r.rows_with_any_missing_pct:.2f}% |" for r in grp.itertuples()]
    out += ["", "## Default rate when missing vs present (clusters over 5% missing; one row per identical-mask cluster)", "",
            f"Flag rule (my EDA convention, adjustable): |gap| >= {INFORMATIVE_MIN_PP:.0f} pp and the Wald 95% CI of the gap excludes 0. Overall default rate 8.07%.", "",
            "Adjusted gap = same comparison inside each NAME_INCOME_TYPE x REGION_RATING_CLIENT stratum, averaged with stratum-size weights (strata with fewer than 30 rows on either side dropped). It asks whether the gap survives once two observed variables are held fixed.", "",
            "| Cluster | Columns | Missing % | Rate when missing (n) | Rate when present (n) | Gap pp [95% CI] | Adjusted gap pp (rows used) | Flag |", "|---|---|---|---|---|---|---|---|"]
    for r in gaps.sort_values("missing_pct", ascending=False).itertuples():
        cols = ", ".join(r.cols) if len(r.cols) <= 3 else f"{r.cols[0]}, {r.cols[1]}, ... ({len(r.cols)} cols)"
        out.append(f"| {r.cluster} | {cols} | {r.missing_pct:.2f} | {r.rate_missing_pct:.2f}% ({r.n_missing:,}) | {r.rate_present_pct:.2f}% ({r.n_present:,}) | {r.gap_pp:+.2f} [{r.ci_lo_pp:+.2f}, {r.ci_hi_pp:+.2f}] | {r.adj_gap_pp:+.2f} ({r.adj_used:.0%}) | {'FLAG' if r.informative else ''} |")
    flagged = gaps[gaps["informative"]]
    out += ["", f"- Flagged clusters: {len(flagged)} of {len(gaps)}, covering {int(flagged['n_cols'].sum())} of {int(gaps['n_cols'].sum())} columns.", ""]

    # co-missing
    out += ["## Which missing patterns go together", ""]
    iu = np.triu_indices_from(phi.to_numpy(), 1)
    pairs = sorted(zip(phi.to_numpy()[iu], phi.index[iu[0]], phi.columns[iu[1]]), reverse=True)
    out += ["Top 10 pairs of different clusters by phi:", "", "| phi | A | B |", "|---|---|---|"]
    out += [f"| {p:.3f} | {a} | {b} |" for p, a, b in pairs[:10]]
    out += ["", f"- Pairs of clusters with phi >= 0.5: {sum(1 for p, _, _ in pairs if p >= 0.5)} of {len(pairs)}; phi < 0.1: {sum(1 for p, _, _ in pairs if p < 0.1)}.", ""]
    out += ["Cluster membership for building columns and others over 5% (cluster, missing %, columns):", ""]
    for cl in big:
        out.append(f"- M{cluster_of[cl[0]]:02d} ({miss_pct[cl[0]]:.2f}%): {', '.join(cl)}")
    out.append("")

    out += ["## Does missingness depend on an observed variable? (Cramer's V, top 3 covariates per cluster)", "",
            "Covariates are fully observed columns; numerics are cut into 5 quantile bins. V near 0 means no link, near 1 means the missing pattern is almost determined by the covariate.", "",
            "| Cluster | 1st | 2nd | 3rd |", "|---|---|---|---|"]
    out += [f"| {lab} | " + " | ".join(f"{c} {v:.2f}" for c, v in top) + " |" for lab, top in probe]
    out.append("")

    # ---- selected cross-checks that the written notes quote ----
    bur = df["AMT_REQ_CREDIT_BUREAU_YEAR"].isna()
    age_bin = pd.qcut(-df["DAYS_BIRTH"] / 365.25, 5)
    es1_by_age = df["EXT_SOURCE_1"].isna().groupby(age_bin, observed=True).mean()
    nonpens = df["NAME_INCOME_TYPE"] != "Pensioner"
    bld = [cl[0] for cl in big if column_group(cl[0]) == "Building / housing attributes"]
    pb = phi.loc[bld, bld].to_numpy()
    es1_phi = phi.loc["EXT_SOURCE_1"].drop("EXT_SOURCE_1")
    out += ["## Selected cross-checks", "",
            f"- Building patterns over 5%: {len(bld)} of {len(big)}. Pairwise phi among them: min {pb[np.triu_indices_from(pb, 1)].min():.3f}, max {pb[np.triu_indices_from(pb, 1)].max():.3f}.",
            f"- EXT_SOURCE_1 pattern: largest phi with any other pattern is {es1_phi.max():.3f} ({es1_phi.idxmax()}).",
            f"- EXT_SOURCE_3 missing when the bureau-enquiry block is missing: {df.loc[bur, 'EXT_SOURCE_3'].isna().mean():.2%} (n={int(bur.sum()):,}); when it is present: {df.loc[~bur, 'EXT_SOURCE_3'].isna().mean():.2%} (n={int((~bur).sum()):,}).",
            "- EXT_SOURCE_1 missing by age quintile: " + "; ".join(f"{str(k)} {v:.1%}" for k, v in es1_by_age.items()),
            f"- OCCUPATION_TYPE missing among non-pensioners: {df.loc[nonpens, 'OCCUPATION_TYPE'].isna().mean():.2%} (n={int(nonpens.sum()):,}); among pensioners: {df.loc[~nonpens, 'OCCUPATION_TYPE'].isna().mean():.2%} (n={int((~nonpens).sum()):,}).",
            f"- OWN_CAR_AGE missing among FLAG_OWN_CAR = N: {df.loc[df['FLAG_OWN_CAR'] == 'N', 'OWN_CAR_AGE'].isna().mean():.2%}; among Y: {df.loc[df['FLAG_OWN_CAR'] == 'Y', 'OWN_CAR_AGE'].isna().mean():.2%}.",
            f"- Bureau counts that are 0 among non-missing rows: AMT_REQ_CREDIT_BUREAU_YEAR = 0 in {(df['AMT_REQ_CREDIT_BUREAU_YEAR'] == 0).sum():,} rows ({(df['AMT_REQ_CREDIT_BUREAU_YEAR'] == 0).mean():.2%} of all rows).", ""]

    out += ["## Missing fields per row and default rate", "", "| Missing fields in row | Rows | % of rows | Default rate |", "|---|---|---|---|"]
    out += [f"| {i} | {int(r['size']):,} | {r['size'] / n:.2%} | {r['mean']:.2%} |" for i, r in rowtab.iterrows()]
    out.append("")
    (REPORT_DIR / "section5_facts.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
