# Section 5: missingness baseline

Train split only. Labels: [DATA] verified by code (`section5_facts.md`, `missingness_by_feature.csv`, `missingness_by_group.csv`), [GENERAL] domain knowledge, hypotheses marked as hypotheses. Charts are in `figures/` (`missingness_by_group.png`, `missingness_cluster_corr.png`, `missingness_default_gap.png`).

## The headline [DATA]

- 67 of 122 columns have at least one missing value. 57 have more than 5%. 41 have more than 50%.
- Only 5,134 rows (2.78%) have no missing value in any column. The median row has 36 missing fields.
- So dropping incomplete rows is not an option. It would remove 97% of the data.
- The 67 columns collapse into 31 distinct missing patterns. Columns in one pattern are missing in exactly the same rows. 24 of those patterns are above 5%.

## By group [DATA]

| Group | Columns | With missing | Over 5% | Mean missing % | Rows with any missing in group |
|---|---|---|---|---|---|
| Building / housing attributes | 47 | 47 | 47 | 57.80 | 74.37% |
| External scores | 3 | 3 | 2 | 25.48 | 64.42% |
| Assets (OWN_CAR_AGE) | 3 | 1 | 1 | 22.01 | 66.04% |
| Credit bureau enquiries | 6 | 6 | 6 | 13.48 | 13.48% |
| Income and employment (OCCUPATION_TYPE) | 5 | 1 | 1 | 6.28 | 31.38% |
| Social circle | 4 | 4 | 0 | 0.34 | 0.34% |
| Client demographics | 8 | 2 | 0 | 0.05 | 0.42% |
| Loan terms | 4 | 2 | 0 | 0.02 | 0.09% |
| Application timing and history | 5 | 1 | 0 | 0.00 | 0.00% |
| Region, contact flags, document flags, ID and label | 2, 9, 6, 20 | 0 | 0 | 0.00 | 0.00% |

Note: 55 columns have no missing value at all. They are the only columns where any missingness in a later experiment would be purely injected.

## What goes missing together [DATA]

- The building block is a single story. 19 of the 24 over-5% patterns are building columns. Pairs of building patterns correlate at 0.62 to 0.99 (phi, the correlation of 0/1 missing flags). Across all 24 patterns, 172 of 276 pairs have phi of 0.5 or more.
- Outside the building block, three separate stories:
  - OWN_CAR_AGE: missing in 100.00% of rows where FLAG_OWN_CAR = N, and in 0.01% where it is Y.
  - OCCUPATION_TYPE: missing in 99.99% of pensioners (n=33,218) and 16.31% of everyone else (n=151,288).
  - EXT_SOURCE_3 and the 6 credit bureau enquiry counts: when the bureau block is missing (n=24,878), EXT_SOURCE_3 is missing in 100.00% of those rows. When the bureau block is present it is missing in 7.32%. The bureau block is nested inside EXT_SOURCE_3 missingness.
- EXT_SOURCE_1 is on its own. Its pattern has low correlation with every other pattern (phi at most 0.129, with OCCUPATION_TYPE). It is missing in 41.5% of the youngest quintile and 77.3% of the oldest. [DATA]

## Is missingness itself informative? [DATA]

Method: for each pattern over 5% missing, default rate when missing minus default rate when present, with a 95% confidence interval (Wald). I flag a pattern if the gap is at least 1 percentage point and the interval excludes 0. The 1 point cut is my EDA convention, not a project rule. Overall default rate is 8.07%.

| Pattern | Missing % | Rate when missing | Rate when present | Gap pp | Gap after adjusting for income type and region rating |
|---|---|---|---|---|---|
| Bureau enquiries (6 cols) | 13.48 | 10.53% | 7.69% | +2.84 | +2.77 |
| Building patterns (19) | 47 to 70 | 8.56% to 9.22% | 6.93% to 7.05% | +1.57 to +2.18 | +1.29 to +1.74 |
| EXT_SOURCE_3 | 19.82 | 9.35% | 7.76% | +1.59 | +1.54 |
| EXT_SOURCE_1 | 56.39 | 8.53% | 7.49% | +1.04 | +1.52 |
| OWN_CAR_AGE | 66.04 | 8.49% | 7.26% | +1.23 | +1.59 |
| OCCUPATION_TYPE | 31.38 | 6.57% | 8.76% | -2.20 | -0.49 |

- All 24 patterns are flagged. That is a weak filter. With 184,506 rows, a 1 point gap is easy to detect. Read the size of the gap, not the flag.
- The sizes are small to moderate. The largest is the bureau block at +2.84 points. A row missing 41 to 60 fields defaults at 9.16% versus 6.02% for complete rows. [DATA]
- OCCUPATION_TYPE is the one pattern that mostly disappears after adjustment (-2.20 to -0.49). The raw gap is largely the pensioner effect. This is the only case where the raw number would mislead.
- The adjustment holds fixed only two observed variables. It is not a causal test. Correlation is not causation.
- The CSV has this table for every column over 5% missing, with n on both sides.

## MCAR, MAR, MNAR in plain words

| Term | Meaning | Example from this data |
|---|---|---|
| MCAR (missing completely at random) | Missingness has no link to anything, seen or unseen. | None of our patterns fit. Even the weakest-linked one (EXT_SOURCE_3) relates to default. |
| MAR (missing at random) | Missingness depends on other columns we can see, but not on the missing value itself, once those are known. | OWN_CAR_AGE is missing exactly when FLAG_OWN_CAR = N. OCCUPATION_TYPE is missing for pensioners. |
| MNAR (missing not at random) | Missingness depends on the missing value itself, or on something unseen. | Not provable from this data. See below. |

Important limit: the data alone cannot prove MNAR, because the value we would need to check is the one that is missing. We can only show that missingness is or is not tied to variables we observe. So everything below is a hypothesis.

| Pattern | Looks like | Why (hypothesis) |
|---|---|---|
| OWN_CAR_AGE | Structural MAR ("not applicable") | 100% missing for non-owners. The value does not exist. |
| OCCUPATION_TYPE | Mostly structural MAR | 99.99% of pensioners missing. The other 16% is unexplained. Cramer's V with NAME_INCOME_TYPE is 0.69 (0 is no link, 1 is a perfect link). |
| Building block | MAR or MNAR, cannot tell | Weak link to observed variables (V 0.13 to 0.17 with region rating, 0.10 to 0.13 with income). The 19 patterns overlap heavily, which fits one failed lookup with different field coverage. The gap survives adjustment. |
| EXT_SOURCE_1 | MAR on age, possibly more | Missing share rises with age from 41.5% to 77.3%. V with age is 0.27, the strongest link of any cluster outside the structural cases. |
| EXT_SOURCE_3 and bureau block | Possibly MNAR | Weak link to every observed variable I checked (V at most 0.08 for EXT_SOURCE_3, 0.09 for the bureau block). Related to default. Nested block structure suggests one shared upstream lookup. Hypothesis only. |
| Social circle, small demographics | Unclear, tiny | Under 0.5% missing. |

## What this means for Scenario A (MNAR missingness)

These are observations and hypotheses. They are not decisions about the experiment.

1. **Severity 0% is not a clean baseline.** The data already has natural missingness in 67 columns. Any injected missingness lands on top of it. The write-up must say that "0%" means "natural level", not "none".
2. **Natural missingness already carries signal.** The gaps above are 1 to 3 points. A scorecard that gives "missing" its own bin and an XGBoost model that handles NaN natively can both use it. Corrupting a column changes how much of that signal survives. Hypothesis: how each model treats missing values may matter as much as the model type. That should be a deliberate design choice.
3. **MNAR cannot be verified in real data, but it can be simulated.** Injecting missingness that depends on the value itself (for example, hiding high incomes more often) is possible because we know the true value. That is the strength of the controlled design.
4. **Columns with no natural missingness give a clean test.** 55 columns are fully observed. Whether that matters for choosing targets belongs to Section 8 and to your decision.
5. **Check the 41 to 60 missing-fields row group.** It holds 49.1% of rows. Anything learned about "rows with a lot of missing" is mostly learned about the building block.

## Questions for you

- Should natural missingness be left as is (my default), or should the clean baseline be imputed first? This changes what "0%" means. It is your decision.
- Do you want the 1 point flag rule kept? It flags everything. A stricter cut (for example 2 points) would flag the bureau block and most building patterns only.
