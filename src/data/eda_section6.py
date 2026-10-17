"""Univariate and bivariate EDA on the train split (EDA session, Section 6).

Reads data/processed/train.csv ONLY. Writes to reports/eda/:
  numeric_summary.csv, categorical_summary.csv, bivariate_numeric_bins.csv,
  bivariate_signal_ranking.csv, bivariate_binary_flags.csv, correlation_top_pairs.csv,
  section6_facts.md, and figures in figures/.

Descriptive only. No WOE, no IV, no models. The bin spread used to rank signals is a
plain default-rate range across decile bins, with a permutation reference for noise.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from src.data.eda import DAYS_EMPLOYED_SENTINEL, column_group  # noqa: E402
from src.data.feature_catalog import semantic_type  # noqa: E402

SEED = 42
ROOT = Path(__file__).resolve().parents[2]
TRAIN_PATH = ROOT / "data" / "processed" / "train.csv"
REPORT_DIR = ROOT / "reports" / "eda"
FIG_DIR = REPORT_DIR / "figures"

N_BINS = 10
MIN_BIN_N = 500  # bins smaller than this are ignored when computing the rate range
RARE_PCT = 1.0  # a category is "rare" below this share of rows
N_PERM = 5
BUILDING_RE = re.compile(r"^(.*)_(AVG|MODE|MEDI)$")

INK, INK2, GRID, BLUE, GREY, ORANGE = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6", "#9a9992", "#eb6834"


# ---------------------------------------------------------------- helpers (pure)
def clean_series(name: str, s: pd.Series) -> pd.Series:
    """DAYS_EMPLOYED placeholder becomes NaN so it cannot distort statistics. Pure."""
    if name == "DAYS_EMPLOYED":
        return s.where(s != DAYS_EMPLOYED_SENTINEL)
    return s


def wilson(k: np.ndarray, n: np.ndarray, z: float = 1.96) -> tuple[np.ndarray, np.ndarray]:
    """Wilson 95% interval for a proportion. Pure."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    p = np.divide(k, n, out=np.zeros_like(k), where=n > 0)
    denom = 1 + z**2 / np.where(n > 0, n, 1)
    centre = (p + z**2 / (2 * np.where(n > 0, n, 1))) / denom
    half = z * np.sqrt(p * (1 - p) / np.where(n > 0, n, 1) + z**2 / (4 * np.where(n > 0, n, 1) ** 2)) / denom
    return centre - half, centre + half


def suggest_treatment(name: str, s: pd.Series, stype: str) -> str:
    """Rule-based treatment suggestion (a proposal, not a decision). Pure."""
    notes = []
    if name == "DAYS_EMPLOYED":
        notes.append(f"replace {DAYS_EMPLOYED_SENTINEL} with NaN and add a flag")
    x = clean_series(name, s).dropna()
    if x.empty:
        return "n/a"
    p99, mx = x.quantile(0.99), x.max()
    if s.isna().mean() > 0.5:
        notes.append("keep missing as its own bin (>50% missing)")
    if stype == "numeric count" and p99 > 0 and mx / p99 > 5:
        notes.append("cap at p99.9 or merge the upper tail into one bin")
    elif stype == "numeric continuous" and x.min() > 0 and x.skew() > 2:
        notes.append("log scale or quantile bins")
    elif stype == "numeric continuous" and p99 > 0 and mx / p99 > 5:
        notes.append("cap at p99.9")
    return "; ".join(notes) if notes else "none needed"


def assign_bins(x: pd.Series, n_bins: int = N_BINS) -> tuple[np.ndarray, list[str]]:
    """Bin codes (0..k-1; missing gets the last code, labelled 'missing') and labels. Pure."""
    nonnull = x.dropna()
    if nonnull.nunique() <= 12:
        vals = sorted(nonnull.unique().tolist())
        lookup = {v: i for i, v in enumerate(vals)}
        codes = x.map(lookup).to_numpy(dtype=float)
        labels = [f"{v:g}" for v in vals]
    else:
        q = pd.qcut(x, n_bins, duplicates="drop")
        codes = q.cat.codes.to_numpy(dtype=float)
        codes[codes < 0] = np.nan
        labels = [f"({iv.left:,.4g}, {iv.right:,.4g}]" for iv in q.cat.categories]
    if np.isnan(codes).any():
        codes = np.where(np.isnan(codes), len(labels), codes)
        labels = labels + ["missing"]
    return codes.astype(int), labels


def bin_table(y: np.ndarray, codes: np.ndarray, labels: list[str]) -> pd.DataFrame:
    n = np.bincount(codes, minlength=len(labels))
    d = np.bincount(codes, weights=y, minlength=len(labels))
    lo, hi = wilson(d, n)
    return pd.DataFrame({"bin": labels, "n": n, "defaults": d.astype(int),
                         "rate_pct": np.divide(d, n, out=np.zeros(len(n)), where=n > 0) * 100,
                         "ci_lo_pct": lo * 100, "ci_hi_pct": hi * 100})


def rate_range(tab: pd.DataFrame, min_n: int = MIN_BIN_N) -> tuple[float, int]:
    """Max minus min default rate (pp) over non-missing bins with at least min_n rows. Pure."""
    t = tab[(tab["bin"] != "missing") & (tab["n"] >= min_n)]
    if len(t) < 2:
        return float("nan"), len(t)
    return float(t["rate_pct"].max() - t["rate_pct"].min()), len(t)


def null_range(y: np.ndarray, codes: np.ndarray, labels: list[str], rng: np.random.Generator, reps: int = N_PERM) -> float:
    """Average rate range when TARGET is shuffled: what pure noise gives for the same bins. Pure given rng."""
    vals = [rate_range(bin_table(rng.permutation(y), codes, labels))[0] for _ in range(reps)]
    return float(np.nanmean(vals))


def stem_of(col: str) -> str | None:
    m = BUILDING_RE.match(col)
    return m.group(1) if m else None


# ---------------------------------------------------------------- plotting
def _style(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=7.5)


def plot_numeric_panel(df: pd.DataFrame, path: Path) -> None:
    items = [
        ("AMT_INCOME_TOTAL (log10)", np.log10(df["AMT_INCOME_TOTAL"].clip(lower=1))),
        ("AMT_CREDIT", df["AMT_CREDIT"]),
        ("AMT_ANNUITY", df["AMT_ANNUITY"]),
        ("Years employed (placeholder removed)", -clean_series("DAYS_EMPLOYED", df["DAYS_EMPLOYED"]) / 365.25),
        ("OBS_30_CNT_SOCIAL_CIRCLE (clipped at p99.9)", df["OBS_30_CNT_SOCIAL_CIRCLE"].clip(upper=df["OBS_30_CNT_SOCIAL_CIRCLE"].quantile(0.999))),
        ("AMT_REQ_CREDIT_BUREAU_YEAR", df["AMT_REQ_CREDIT_BUREAU_YEAR"]),
        ("OWN_CAR_AGE", df["OWN_CAR_AGE"]),
        ("CNT_CHILDREN (clipped at p99.9)", df["CNT_CHILDREN"].clip(upper=df["CNT_CHILDREN"].quantile(0.999))),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(14, 6))
    for ax, (title, s) in zip(axes.ravel(), items):
        x = s.dropna()
        bins = np.arange(x.min() - 0.5, x.max() + 1.5) if (x.nunique() <= 30 and float(x.min()).is_integer()) else 40
        ax.hist(x, bins=bins, color=BLUE, edgecolor="white", linewidth=0.3)
        ax.set_title(f"{title}\nskew {x.skew():.1f}, n {len(x):,}", fontsize=8, loc="left", color=INK)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        _style(ax)
    fig.suptitle("Numeric columns that need a treatment decision (train)", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_category_panel(cat: pd.DataFrame, columns: list[str], overall: float, path: Path, ncols: int = 3) -> None:
    nrows = int(np.ceil(len(columns) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 2.6 * nrows))
    for ax, col in zip(np.atleast_1d(axes).ravel(), columns):
        full = cat[cat["column"] == col]
        t = full[full["n"] >= 100].sort_values("n")
        hidden = len(full) - len(t)
        ys = np.arange(len(t))
        ax.hlines(ys, t["ci_lo_pct"], t["ci_hi_pct"], color=BLUE, linewidth=1.3)
        ax.plot(t["rate_pct"], ys, "o", color=BLUE, markersize=5, markeredgecolor="white", markeredgewidth=0.8)
        ax.axvline(overall, color=INK2, linewidth=0.8, linestyle="--")
        ax.set_yticks(ys, [f"{str(c)[:24]} (n={n:,})" for c, n in zip(t["category"], t["n"])], fontsize=7)
        ax.set_title(col + (f"  ({hidden} hidden, n<100)" if hidden else ""), fontsize=9, loc="left", color=INK)
        ax.set_xlabel("default rate % (95% CI); dashed = overall", fontsize=7, color=INK2)
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        _style(ax)
    for ax in np.atleast_1d(axes).ravel()[len(columns):]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_org_occ(cat: pd.DataFrame, overall: float, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 10), gridspec_kw={"width_ratios": [1, 1.5]})
    for ax, col, min_n in zip(axes, ["OCCUPATION_TYPE", "ORGANIZATION_TYPE"], [0, 0]):
        t = cat[(cat["column"] == col)].sort_values("rate_pct")
        ys = np.arange(len(t))
        colour = [ORANGE if c in ("(missing)", "XNA") else BLUE for c in t["category"]]
        ax.hlines(ys, t["ci_lo_pct"], t["ci_hi_pct"], color=colour, linewidth=1.2)
        ax.scatter(t["rate_pct"], ys, c=colour, s=22, edgecolor="white", linewidth=0.6, zorder=3)
        ax.axvline(overall, color=INK2, linewidth=0.8, linestyle="--")
        ax.set_yticks(ys, [f"{c} ({n:,})" for c, n in zip(t["category"], t["n"])], fontsize=6.5)
        ax.set_title(f"{col}  (orange = missing or XNA)", fontsize=9, loc="left", color=INK)
        ax.set_xlabel("default rate % (95% CI); dashed = overall; n in brackets", fontsize=7, color=INK2)
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_top_signals(bins: pd.DataFrame, ranking: pd.DataFrame, overall: float, path: Path, k: int = 12) -> None:
    feats = ranking.head(k)["feature"].tolist()
    fig, axes = plt.subplots(3, 4, figsize=(15, 9))
    for ax, f in zip(axes.ravel(), feats):
        t = bins[bins["feature"] == f].reset_index(drop=True)
        hidden = int((t["n"] < MIN_BIN_N).sum())
        t = t[t["n"] >= MIN_BIN_N].reset_index(drop=True)
        colour = [ORANGE if b == "missing" else BLUE for b in t["bin"]]
        ax.bar(range(len(t)), t["rate_pct"], color=colour, width=0.7)
        ax.axhline(overall, color=INK2, linewidth=0.8, linestyle="--")
        r = ranking[ranking["feature"] == f].iloc[0]
        ax.set_title(f"{f}\nrange {r['range_pp']:.1f} pp, Spearman {r['spearman_with_target']:+.3f}" + (f", {hidden} small bins hidden" if hidden else ""), fontsize=8, loc="left", color=INK)
        ax.set_xticks(range(len(t)), [str(i + 1) if b != "missing" else "NA" for i, b in enumerate(t["bin"])], fontsize=7)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        _style(ax)
    fig.suptitle(f"Default rate % by decile bin (bin 1 = lowest values; NA = missing; bins under {MIN_BIN_N} rows hidden). Dashed = overall {overall:.2f}%", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_target_corr(tc: pd.DataFrame, path: Path, k: int = 15) -> None:
    t = tc.head(k).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.35 * k + 1.5))
    ys = np.arange(len(t))
    ax.barh(ys - 0.18, t["spearman"], height=0.34, color=BLUE, label="Spearman")
    ax.barh(ys + 0.18, t["pearson"], height=0.34, color=GREY, label="Pearson")
    ax.set_yticks(ys, t["feature"], fontsize=7.5)
    ax.axvline(0, color=INK2, linewidth=0.8)
    ax.set_xlabel("correlation with TARGET (train, pairwise complete)", fontsize=8, color=INK2)
    ax.set_title("Strongest correlations with TARGET", loc="left", fontsize=11, color=INK)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(TRAIN_PATH)
    n = len(df)
    y = df["TARGET"].to_numpy()
    overall = float(y.mean() * 100)
    rng = np.random.default_rng(SEED)
    stypes = {c: semantic_type(c, df[c]) for c in df.columns}
    out: list[str] = ["# Section 6 facts (train split only)", "",
                      "Generated by `src/data/eda_section6.py`. DAYS_EMPLOYED placeholder 365243 is set to missing in every statistic below.", ""]

    # ---------- numeric summary
    num_cols = [c for c in df.columns if stypes[c] in ("numeric continuous", "numeric count", "ordinal") and df[c].dtype != object]
    rows = []
    for c in num_cols:
        s = df[c]
        x = clean_series(c, s).dropna()
        q1, q3 = x.quantile(0.25), x.quantile(0.75)
        iqr = q3 - q1
        outl = int(((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum()) if iqr > 0 else np.nan
        rows.append({
            "feature": c, "group": column_group(c), "type": stypes[c], "n_nonmissing": len(x),
            "missing_pct": round((1 - len(x) / n) * 100, 2), "mean": x.mean(), "std": x.std(), "skew": x.skew(),
            "min": x.min(), "p1": x.quantile(0.01), "p25": q1, "median": x.median(), "p75": q3,
            "p99": x.quantile(0.99), "p99_9": x.quantile(0.999), "max": x.max(),
            "iqr_outliers_n": outl, "iqr_outliers_pct": (outl / len(x) * 100) if iqr > 0 else np.nan,
            "max_over_p99": (x.max() / x.quantile(0.99)) if x.quantile(0.99) > 0 else np.nan,
            "suggested_treatment": suggest_treatment(c, s, stypes[c]),
        })
    numsum = pd.DataFrame(rows)
    numsum.to_csv(REPORT_DIR / "numeric_summary.csv", index=False, float_format="%.4f")
    treat = numsum[numsum["suggested_treatment"] != "none needed"]
    out += ["## Numeric columns", "",
            f"- Numeric columns summarised (continuous, count, ordinal): {len(numsum)}. Binary flags are handled separately.",
            f"- Columns with a treatment suggestion: {len(treat)} of {len(numsum)}. 'None needed' for {len(numsum) - len(treat)}.",
            f"- Columns with abs(skew) > 2: {int((numsum['skew'].abs() > 2).sum())}; with max / p99 > 5: {int((numsum['max_over_p99'] > 5).sum())}.", "",
            "Columns that got a suggestion (proposal only; trees need none of these, a scorecard bins them anyway):", "",
            "| Feature | Type | Skew | p99 | p99.9 | max | IQR outliers % | Suggestion |", "|---|---|---|---|---|---|---|---|"]
    for r in treat.sort_values("skew", key=abs, ascending=False).itertuples():
        out.append(f"| {r.feature} | {r.type} | {r.skew:.1f} | {r.p99:,.4g} | {r.p99_9:,.4g} | {r.max:,.4g} | {'n/a' if pd.isna(r.iqr_outliers_pct) else f'{r.iqr_outliers_pct:.1f}'} | {r.suggested_treatment} |")
    out += ["", "Note: IQR rule (outside Q1 - 1.5 IQR, Q3 + 1.5 IQR) is n/a when IQR is 0, which is the case for most count columns (median and quartiles are all 0).", ""]
    plot_numeric_panel(df, FIG_DIR / "numeric_treatment_panel.png")

    # ---------- categorical
    cat_cols = [c for c in df.columns if df[c].dtype == object]
    crow = []
    for c in cat_cols:
        s = df[c].fillna("(missing)")
        g = pd.DataFrame({"cat": s, "y": y}).groupby("cat")["y"].agg(["size", "sum"])
        lo, hi = wilson(g["sum"].to_numpy(), g["size"].to_numpy())
        for i, (cat_name, r) in enumerate(g.iterrows()):
            crow.append({"column": c, "category": cat_name, "n": int(r["size"]), "pct_of_rows": r["size"] / n * 100,
                         "defaults": int(r["sum"]), "rate_pct": r["sum"] / r["size"] * 100,
                         "ci_lo_pct": lo[i] * 100, "ci_hi_pct": hi[i] * 100, "lift_vs_overall": r["sum"] / r["size"] * 100 / overall,
                         "rare": bool(r["size"] / n * 100 < RARE_PCT)})
    cat = pd.DataFrame(crow)
    cat.to_csv(REPORT_DIR / "categorical_summary.csv", index=False, float_format="%.4f")
    out += ["## Categorical columns", "",
            f"- {len(cat_cols)} text columns, {len(cat)} (column, category) rows. Rare = under {RARE_PCT:.0f}% of rows.", "",
            "| Column | Categories | Rare | Highest rate (n) | Lowest rate (n) | Range pp (cats with n >= 1,000) |", "|---|---|---|---|---|---|"]
    for c in cat_cols:
        t = cat[cat["column"] == c]
        tb = t[t["n"] >= 1000]
        hi_r = tb.loc[tb["rate_pct"].idxmax()] if len(tb) else t.loc[t["rate_pct"].idxmax()]
        lo_r = tb.loc[tb["rate_pct"].idxmin()] if len(tb) else t.loc[t["rate_pct"].idxmin()]
        out.append(f"| {c} | {len(t)} | {int(t['rare'].sum())} | {hi_r['category']} {hi_r['rate_pct']:.2f}% ({hi_r['n']:,}) | {lo_r['category']} {lo_r['rate_pct']:.2f}% ({lo_r['n']:,}) | {hi_r['rate_pct'] - lo_r['rate_pct']:.2f} |")
    rare = cat[cat["rare"]].sort_values("n")
    out += ["", f"Rare categories in total: {len(rare)}. Smallest 15:", "", "| Column | Category | n | Default rate % |", "|---|---|---|---|"]
    out += [f"| {r.column} | {r.category} | {r.n:,} | {r.rate_pct:.2f} |" for r in rare.head(15).itertuples()]
    out.append("")
    plot_category_panel(cat, ["NAME_CONTRACT_TYPE", "CODE_GENDER", "NAME_INCOME_TYPE", "NAME_EDUCATION_TYPE", "NAME_FAMILY_STATUS", "NAME_HOUSING_TYPE"],
                        overall, FIG_DIR / "categorical_default_rates.png")
    plot_org_occ(cat, overall, FIG_DIR / "categorical_occupation_organization.png")

    # ---------- bivariate numeric
    brows, rank = [], []
    for c in num_cols:
        x = clean_series(c, df[c])
        codes, labels = assign_bins(x)
        tab = bin_table(y, codes, labels)
        tab.insert(0, "feature", c)
        brows.append(tab)
        rng_pp, k_used = rate_range(tab)
        nr = null_range(y, codes, labels, rng)
        ok = x.notna().to_numpy()
        rho = spearmanr(x[ok], y[ok]).statistic
        miss_rate = tab.loc[tab["bin"] == "missing", "rate_pct"]
        rank.append({"feature": c, "group": column_group(c), "range_pp": rng_pp, "null_range_pp": nr,
                     "range_over_null": rng_pp / nr if nr else np.nan, "bins_used": k_used,
                     "spearman_with_target": rho, "abs_spearman": abs(rho),
                     "missing_bin_rate_pct": float(miss_rate.iloc[0]) if len(miss_rate) else np.nan})
    bins = pd.concat(brows, ignore_index=True)
    bins.to_csv(REPORT_DIR / "bivariate_numeric_bins.csv", index=False, float_format="%.4f")
    ranking = pd.DataFrame(rank).sort_values("range_pp", ascending=False).reset_index(drop=True)
    ranking.to_csv(REPORT_DIR / "bivariate_signal_ranking.csv", index=False, float_format="%.4f")
    plot_top_signals(bins, ranking, overall, FIG_DIR / "bivariate_top_signals.png")

    out += ["## Default rate by decile bin: strongest and weakest signals", "",
            f"Method: 10 quantile bins (exact values when a column has 12 or fewer distinct values), missing as its own bin. 'Range' = highest minus lowest bin default rate among non-missing bins with at least {MIN_BIN_N} rows. 'Null range' = the same range after shuffling TARGET (mean of {N_PERM} shuffles, seed {SEED}): what noise alone produces. With about {n // 10:,} rows per decile, one standard error is about {np.sqrt(overall/100*(1-overall/100)/(n/10))*100:.2f} pp.", "",
            "Top 20 by range:", "", "| Feature | Group | Range pp | Null range pp | Spearman | Missing-bin rate % |", "|---|---|---|---|---|---|"]
    out += [f"| {r.feature} | {r.group} | {r.range_pp:.2f} | {r.null_range_pp:.2f} | {r.spearman_with_target:+.3f} | {'' if pd.isna(r.missing_bin_rate_pct) else f'{r.missing_bin_rate_pct:.2f}'} |" for r in ranking.head(20).itertuples()]
    weak = ranking[ranking["range_over_null"] < 2]
    out += ["", f"Features whose range is under 2x the shuffled range (close to noise): {len(weak)} of {len(ranking)}.", "",
            "Bottom 15 by range:", "", "| Feature | Range pp | Null range pp | Spearman |", "|---|---|---|---|"]
    out += [f"| {r.feature} | {r.range_pp:.2f} | {r.null_range_pp:.2f} | {r.spearman_with_target:+.3f} |" for r in ranking.tail(15).itertuples()]
    out += ["", "Decile detail for the top 3 features (n per bin):", ""]
    for f in ranking.head(3)["feature"]:
        t = bins[bins["feature"] == f]
        out += [f"**{f}**", "", "| Bin | n | Default rate % | 95% CI |", "|---|---|---|---|"]
        out += [f"| {r.bin} | {r.n:,} | {r.rate_pct:.2f} | {r.ci_lo_pct:.2f} to {r.ci_hi_pct:.2f} |" for r in t.itertuples()]
        out.append("")

    ca = df["OWN_CAR_AGE"]
    spike = ca[ca >= 60].value_counts().sort_index()
    in_spike = ca.isin([64, 65])
    out += [f"OWN_CAR_AGE spike: rows with age 60 or more by value: {spike.to_dict()}. Ages 64 and 65 together: {int(in_spike.sum()):,} rows ({in_spike.sum() / ca.notna().sum():.2%} of rows with a car age), default rate {y[in_spike.to_numpy()].mean():.2%}; ages 20 to 40 (not 64 or 65): {y[((ca >= 20) & (ca <= 40)).to_numpy()].mean():.2%}. Next-largest age value below 60 has {int(ca[ca < 60].value_counts().max()):,} rows.", ""]
    gp = df["AMT_GOODS_PRICE"]
    top_val = gp.value_counts().index[0]
    mk = gp == top_val
    out += [f"Round-number clump: AMT_GOODS_PRICE equals {top_val:,.0f} in {int(mk.sum()):,} rows ({mk.mean():.2%}), default rate {y[mk.to_numpy()].mean():.2%}; "
            f"{(df.loc[mk, 'NAME_CONTRACT_TYPE'] == 'Cash loans').mean():.1%} of those rows are cash loans. Rows with any other goods price: {y[~mk.to_numpy()].mean():.2%}.", ""]

    # ---------- binary flags
    flag_cols = [c for c in df.columns if stypes[c] == "binary flag" and df[c].dtype != object]
    frow = []
    for c in flag_cols:
        s = df[c]
        n1, n0 = int((s == 1).sum()), int((s == 0).sum())
        r1, r0 = y[(s == 1).to_numpy()].mean() * 100, y[(s == 0).to_numpy()].mean() * 100
        frow.append({"feature": c, "n_1": n1, "pct_1": n1 / n * 100, "rate_when_1_pct": r1, "n_0": n0, "rate_when_0_pct": r0, "diff_pp": r1 - r0})
    flags = pd.DataFrame(frow).sort_values("diff_pp", key=abs, ascending=False)
    flags.to_csv(REPORT_DIR / "bivariate_binary_flags.csv", index=False, float_format="%.4f")
    big = flags[(flags["n_1"] >= MIN_BIN_N) & (flags["n_0"] >= MIN_BIN_N)]
    out += ["## Binary flags (default rate when 1 vs 0)", "",
            f"{len(flags)} numeric flags. Showing the 10 largest differences among flags where both sides have at least {MIN_BIN_N} rows.", "",
            "| Flag | Share of 1s | Rate when 1 (n) | Rate when 0 (n) | Diff pp |", "|---|---|---|---|---|"]
    out += [f"| {r.feature} | {r.pct_1:.2f}% | {r.rate_when_1_pct:.2f}% ({r.n_1:,}) | {r.rate_when_0_pct:.2f}% ({r.n_0:,}) | {r.diff_pp:+.2f} |" for r in big.head(10).itertuples()]
    out.append("")

    # ---------- correlations
    allnum = [c for c in df.columns if df[c].dtype != object and c not in ("SK_ID_CURR", "TARGET")]
    clean = pd.DataFrame({c: clean_series(c, df[c]) for c in allnum})
    corr = clean.corr()
    iu = np.triu_indices_from(corr.to_numpy(), 1)
    pairs = pd.DataFrame({"a": corr.index[iu[0]], "b": corr.columns[iu[1]], "r": corr.to_numpy()[iu]})
    pairs["abs_r"] = pairs["r"].abs()
    pairs["same_building_stem"] = [(stem_of(a) is not None and stem_of(a) == stem_of(b)) for a, b in zip(pairs["a"], pairs["b"])]
    pairs = pairs.sort_values("abs_r", ascending=False)
    pairs.head(200).to_csv(REPORT_DIR / "correlation_top_pairs.csv", index=False, float_format="%.4f")
    nb = pairs[~pairs["same_building_stem"]]
    out += ["## Correlation between features (Pearson, pairwise complete)", "",
            f"- {len(allnum)} numeric columns, {len(pairs):,} pairs. Pairs with abs(r) >= 0.9: {int((pairs['abs_r'] >= 0.9).sum())}; >= 0.8: {int((pairs['abs_r'] >= 0.8).sum())}; >= 0.7: {int((pairs['abs_r'] >= 0.7).sum())}.",
            f"- Of the pairs with abs(r) >= 0.9, {int(((pairs['abs_r'] >= 0.9) & pairs['same_building_stem']).sum())} are AVG / MODE / MEDI twins of the same building stem.",
            f"- Pairs with abs(r) >= 0.9 that are NOT building twins: {int((nb['abs_r'] >= 0.9).sum())}; >= 0.8: {int((nb['abs_r'] >= 0.8).sum())}.", "",
            "Top 15 pairs excluding same-stem building twins (cross-stem building pairs still dominate):", "", "| A | B | r |", "|---|---|---|"]
    out += [f"| {r.a} | {r.b} | {r.r:+.3f} |" for r in nb.head(15).itertuples()]
    bset = {c for c in allnum if column_group(c) == "Building / housing attributes"}
    nobld = pairs[~pairs["a"].isin(bset) & ~pairs["b"].isin(bset)]
    out += ["", f"Top 20 pairs with no building column at all ({int((nobld['abs_r'] >= 0.8).sum())} pairs with abs(r) >= 0.8, {int((nobld['abs_r'] >= 0.5).sum())} with >= 0.5):", "", "| A | B | r |", "|---|---|---|"]
    out += [f"| {r.a} | {r.b} | {r.r:+.3f} |" for r in nobld.head(20).itertuples()]
    out.append("")

    tc_rows = []
    for c in allnum:
        x = clean[c]
        ok = x.notna().to_numpy()
        tc_rows.append({"feature": c, "group": column_group(c), "pearson": float(np.corrcoef(x[ok], y[ok])[0, 1]),
                        "spearman": float(spearmanr(x[ok], y[ok]).statistic), "n_used": int(ok.sum())})
    tc = pd.DataFrame(tc_rows)
    tc["abs_best"] = tc[["pearson", "spearman"]].abs().max(axis=1)
    tc = tc.sort_values("abs_best", ascending=False).reset_index(drop=True)
    tc.to_csv(REPORT_DIR / "correlation_with_target.csv", index=False, float_format="%.4f")
    plot_target_corr(tc, FIG_DIR / "target_correlations.png")
    out += ["## Correlation with TARGET", "",
            "Pearson with a 0/1 target is a rough guide only: it measures a straight-line link, it is pulled by outliers, and its maximum for a continuous feature is well below 1 when defaults are rare. Spearman uses ranks, so it ignores outliers but still only sees one-directional trends. Neither shows U-shapes or interactions.", "",
            "| Feature | Group | Pearson | Spearman | n used |", "|---|---|---|---|---|"]
    out += [f"| {r.feature} | {r.group} | {r.pearson:+.4f} | {r.spearman:+.4f} | {r.n_used:,} |" for r in tc.head(20).itertuples()]
    out += ["", f"- Columns with best abs(correlation) under 0.01: {int((tc['abs_best'] < 0.01).sum())} of {len(tc)}; under 0.03: {int((tc['abs_best'] < 0.03).sum())}; over 0.10: {int((tc['abs_best'] > 0.10).sum())}.", ""]

    (REPORT_DIR / "section6_facts.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
