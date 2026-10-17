# Section 6: univariate and bivariate EDA

Train split only. Labels: [DATA] verified by code (`section6_facts.md` and the CSVs in this folder), [GENERAL] domain knowledge, hypotheses marked. The DAYS_EMPLOYED placeholder (365243) is treated as missing in every number below.

Figures in `figures/`: `numeric_treatment_panel.png`, `categorical_default_rates.png`, `categorical_occupation_organization.png`, `bivariate_top_signals.png`, `target_correlations.png`.

## Numeric columns [DATA]

- 72 numeric columns (continuous, count, ordinal) are summarised in `numeric_summary.csv`: mean, std, skew, percentiles up to p99.9, max, IQR outlier counts, and a suggested treatment.
- 45 of 72 have absolute skew above 2. 12 have max more than 5 times the p99.
- The IQR rule is not usable for most count columns. Their quartiles are all 0, so every non-zero value would count as an outlier. The CSV shows n/a there. Percentiles (p99, p99.9, max) are the better guide.
- The treatment column is a proposal. Tree models need none of these changes. A scorecard bins the columns anyway.

Columns that need a real decision (the rest of the 48 flagged columns are building columns where the only suggestion is "keep missing as its own bin"):

| Column | What the data shows | Proposal |
|---|---|---|
| AMT_INCOME_TOTAL | Skew 343.7. p99 472,500, p99.9 900,000, max 117,000,000. | Log scale or quantile bins. Cap at p99.9. |
| DAYS_EMPLOYED | Placeholder in 33,225 rows (18.01%). Real values run from -17,583 to 0. | Replace the placeholder with missing and add a flag. |
| OBS_30 / OBS_60 social circle | Skew 17.6 / 17.5. p99 is 10, max 348 / 344. | Cap at p99.9 (17 / 16), or merge the upper tail. |
| DEF_30 / DEF_60 social circle | p99 is 2, max 34 / 24. | Cap or merge the upper tail. |
| AMT_REQ_CREDIT_BUREAU_MON / QRT / WEEK | Max 27 / 19 / 8 against p99 of 4 / 2 / 1. | Cap or merge the upper tail. |
| CNT_CHILDREN | p99 is 3, max 19. | Cap. |
| NONLIVINGAPARTMENTS (3 flavours) | Skew about 16. p99 near 0.1, p99.9 near 1. | Quantile bins. |
| OWN_CAR_AGE | See the spike below. | Decide after the spike is understood. |

Two quirks found while checking, not in your list:

1. **OWN_CAR_AGE spike.** Among rows with a car age of 60 or more: age 63 has 1 row, age 64 has 1,474, age 65 has 518, and nothing else until 91 (2 rows). Ages 64 and 65 together are 1,992 rows (3.18% of rows with a car age). The next most common single age below 60 has 4,460 rows. A spike next to an empty gap looks like a cap or placeholder. That is a hypothesis, not verified. Default rate in the spike is 8.33%.
2. **AMT_GOODS_PRICE clump at 450,000.** 15,614 rows (8.46%) have exactly this value. Their default rate is 13.67% against 7.56% for all other rows. 95.3% of them are cash loans. Why this value is common and risky is not known. Hypothesis: a standard product tier. Not verified.

## Categorical columns [DATA]

- 16 text columns, 146 (column, category) pairs, 67 rare pairs (under 1% of rows). 41 of the 58 `ORGANIZATION_TYPE` categories are rare.
- Rare categories give unreliable rates. Examples: NAME_INCOME_TYPE "Unemployed" shows 26.67% on 15 rows, and "Student", "Businessman" and "Maternity leave" show 0% on 8, 7 and 2 rows. Do not read these as signals. Proposal: pool them before any scorecard.

Largest spreads (categories with at least 1,000 rows):

| Column | Highest rate (n) | Lowest rate (n) | Range pp |
|---|---|---|---|
| OCCUPATION_TYPE | Low-skill Laborers 18.63% (1,245) | Accountants 4.49% (5,885) | 14.15 |
| ORGANIZATION_TYPE | Construction 12.19% (4,051) | Military 4.73% (1,628) | 7.46 |
| NAME_HOUSING_TYPE | Rented apartment 12.79% (2,909) | Office apartment 6.66% (1,576) | 6.13 |
| NAME_EDUCATION_TYPE | Lower secondary 10.87% (2,272) | Higher education 5.42% (44,721) | 5.46 |
| WALLSMATERIAL_MODE | Wooden 9.81% (3,170) | Monolithic 4.43% (1,062) | 5.39 |
| NAME_INCOME_TYPE | Working 9.52% (95,140) | Pensioner 5.40% (33,218) | 4.12 |
| NAME_FAMILY_STATUS | Single / not married 9.92% (27,350) | Widow 5.89% (9,627) | 4.03 |
| CODE_GENDER | M 10.13% (63,078) | F 7.01% (121,426) | 3.12 |

- Near noise: WEEKDAY_APPR_PROCESS_START (0.53 pp range) and FLAG_OWN_REALTY (0.32 pp).
- In the building text columns, the "(missing)" category has a higher rate than the observed ones, which repeats the Section 5 finding. Example: `EMERGENCYSTATE_MODE` missing 9.22% vs "No" 7.01%.
- `ORGANIZATION_TYPE` = XNA (33,225 rows) has a default rate of 5.4%. It is the same set of rows as the DAYS_EMPLOYED placeholder, which is the pensioners.

## Bivariate: default rate by decile bin [DATA]

Method: 10 quantile bins per numeric column (exact values when a column has 12 or fewer distinct values), missing as its own bin. "Range" is the highest minus the lowest bin default rate, among non-missing bins with at least 500 rows. To see what noise alone gives, I also shuffled TARGET (5 shuffles, seed 42) and recomputed the range. One decile has about 18,450 rows, so one standard error on a bin rate is about 0.20 pp. Everything is in `bivariate_numeric_bins.csv` and `bivariate_signal_ranking.csv`, with n per bin and a 95% interval.

Top signals:

| Feature | Range pp | Shuffled range pp | Spearman | Note |
|---|---|---|---|---|
| EXT_SOURCE_3 | 16.31 | 0.87 | -0.165 | 19.61% in the lowest decile, 3.30% in the highest |
| EXT_SOURCE_2 | 15.46 | 0.63 | -0.147 | 18.29% to 2.84% |
| EXT_SOURCE_1 | 14.25 | 1.00 | -0.150 | 16.88% to 2.62% |
| AMT_GOODS_PRICE | 8.22 | 0.60 | -0.031 | Not a straight line. Peak at the 450,000 clump. |
| DAYS_EMPLOYED | 7.25 | 0.61 | +0.081 | Shorter employment, higher default |
| DAYS_BIRTH | 6.81 | 0.59 | +0.078 | Younger applicants default more |
| REGION_RATING_CLIENT_W_CITY | 6.70 | 0.16 | +0.062 | 3 levels |
| REGION_RATING_CLIENT | 6.41 | 0.24 | +0.060 | 3 levels |

- Missing bins carry information too: EXT_SOURCE_3 missing is 9.35% (n=36,560), EXT_SOURCE_1 missing is 8.53% (n=104,043), both a little above the 8.07% average and far below the lowest decile, so missing is not a "worst" group.
- The DAYS_EMPLOYED missing bin (the placeholder, n=33,225) has 5.41%, the lowest. That is the pensioner effect.
- 15 of 72 columns have a range under twice the shuffled range, so they are close to noise. The weakest are AMT_REQ_CREDIT_BUREAU_WEEK (0.08 pp), _HOUR (0.62), _YEAR (1.35), _MON (1.44), OBS_30 and OBS_60 (about 1.1), and most NONLIVING* building columns.
- Binary flags (`bivariate_binary_flags.csv`, flags with at least 500 rows on both sides): FLAG_DOCUMENT_13 (-5.66 pp, only 617 rows are 1), REG_CITY_NOT_LIVE_CITY (+4.62 pp, 12.34% vs 7.71%, 14,373 rows), FLAG_DOCUMENT_3 (+2.64 pp, 131,010 rows are 1). FLAG_EMP_PHONE (+3.25 pp) is the pensioner flag again.

**Why correlation alone misleads here.** Spearman for AMT_GOODS_PRICE is -0.031 and for AMT_ANNUITY is -0.001, yet their decile default rates range by 8.2 and 4.3 points. AMT_ANNUITY rises from 7.25% to 10.00% and then falls to 5.73% in the top decile. A single correlation number cannot show a hump. This is a plain example for the write-up of why bins or trees pick up more than a straight line.

## Correlation between features [DATA]

- 104 numeric columns, 5,356 pairs. 62 pairs have absolute Pearson r of 0.9 or more. 42 of those are AVG / MODE / MEDI twins. 20 are not twins, but most of those still involve building columns from different stems (for example APARTMENTS_AVG and LIVINGAPARTMENTS_AVG at +0.943).
- Pairs with no building column at all (r of 0.8 or more):

| A | B | r |
|---|---|---|
| OBS_30_CNT_SOCIAL_CIRCLE | OBS_60_CNT_SOCIAL_CIRCLE | +0.999 |
| AMT_CREDIT | AMT_GOODS_PRICE | +0.987 |
| REGION_RATING_CLIENT | REGION_RATING_CLIENT_W_CITY | +0.950 |
| CNT_CHILDREN | CNT_FAM_MEMBERS | +0.879 |
| REG_REGION_NOT_WORK_REGION | LIVE_REGION_NOT_WORK_REGION | +0.863 |
| DEF_30_CNT_SOCIAL_CIRCLE | DEF_60_CNT_SOCIAL_CIRCLE | +0.860 |
| REG_CITY_NOT_WORK_CITY | LIVE_CITY_NOT_WORK_CITY | +0.827 |

- Moderate links worth knowing: DAYS_BIRTH with FLAG_EMP_PHONE +0.620, and DAYS_BIRTH with EXT_SOURCE_1 -0.601. The second means EXT_SOURCE_1 partly tracks age. Whether it acts as an age proxy is a hypothesis, and it matters for the sensitive-attribute question from Section 3.

## Correlation with TARGET [DATA]

Pearson with a 0/1 target is a rough guide only. It sees straight lines, outliers pull it, and it cannot reach 1 when defaults are rare. Spearman uses ranks, so it is steadier, but it still sees only one-directional trends. Neither shows hump shapes or interactions. Correlation is not causation.

| Feature | Pearson | Spearman |
|---|---|---|
| EXT_SOURCE_3 | -0.1765 | -0.1647 |
| EXT_SOURCE_2 | -0.1598 | -0.1468 |
| EXT_SOURCE_1 | -0.1533 | -0.1496 |
| DAYS_EMPLOYED | +0.0763 | +0.0815 |
| DAYS_BIRTH | +0.0779 | +0.0780 |
| REGION_RATING_CLIENT_W_CITY | +0.0621 | +0.0621 |
| REGION_RATING_CLIENT | +0.0600 | +0.0599 |

- Only 3 of 104 columns exceed 0.10 in absolute value. 66 are under 0.03 and 33 are under 0.01.
- Hypothesis: single-column signal is weak, so a model gets most of its lift by combining many weak columns and a few nonlinear shapes. This is where a complex model could beat a scorecard, so it bears on the project question. Not tested here.

## Items for you

- OWN_CAR_AGE spike and the AMT_GOODS_PRICE 450,000 clump: neither is explained. Do you know of a Home Credit convention for them? If not, they stay "unexplained" in the write-up.
- EXT_SOURCE_1 tracks age (r = -0.60). If age is dropped as a sensitive attribute, EXT_SOURCE_1 partly brings it back. Your call for Section 7.
