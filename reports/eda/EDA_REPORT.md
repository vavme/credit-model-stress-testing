# EDA report: Credit Risk Under Data Quality Degradation

Phase 1, Home Credit Default Risk, `application_train.csv` only. All numbers are from the train split (60%) unless stated. Evidence labels: [DATA] checked by code, [DOC] from the column description file, [GENERAL] domain knowledge not checked here. Hypotheses are marked. Nothing in this report is a project decision. Decisions are listed in the last section.

## 1. Dataset overview

- One row is one loan in the sample. `SK_ID_CURR` is a loan ID, not a person ID. [DOC] There are 307,511 loans and 122 columns. [DATA]
- `TARGET` = 1 means a late payment beyond X days in the first Y installments. [DOC] X and Y are not given. It is a payment-difficulty flag, not a write-off or a loss.
- Every row has an outcome, so every row is a granted loan. Rejected applicants are not in the table. [GENERAL, inferred] A model built here ranks people who already passed the lender's screen.
- There is no calendar date. [DATA] The `DAYS_*` columns are offsets from the application day. This allows a clean random split. Any drift in the project is drift we add ourselves.
- Currency and country are not stated. [DATA]
- The six auxiliary tables (bureau, bureau_balance, previous_application, POS_CASH_balance, credit_card_balance, installments_payments) are excluded and were not loaded. [DOC]

## 2. Integrity and split

| Check | Result [DATA] |
|---|---|
| Duplicate rows | 0 |
| Duplicate `SK_ID_CURR` | 0 |
| `TARGET` missing | 0. Values are 0 and 1 only. |
| Constant columns (train) | none |
| Dtypes (train) | 65 float, 41 int, 16 text |
| Raw file | not modified (sha256 unchanged after the run) |

The split is the one already locked in the repo: stratified 60/20/20, seed 42. I re-derived it in memory and confirmed the train part matches `data/processed/train.csv`. I did not open `val.csv` or `test.csv`.

| Split | Rows | Defaults | Rate |
|---|---|---|---|
| train | 184,506 | 14,895 | 8.0729% |
| val | 61,502 | 4,965 | 8.0729% |
| test | 61,503 | 4,965 | 8.0728% |

Row indices are in `data/interim/split_indices.csv` (CSV, because parquet needs a new dependency).

## 3. Feature catalog summary

`feature_catalog.csv` has one row per column with its official description. All 122 columns have a description entry.

| Group | Columns |
|---|---|
| Building and housing (AVG / MODE / MEDI) | 47 |
| Document flags | 20 |
| Region and address consistency | 9 |
| Client demographics | 8 |
| Contact flags | 6 |
| Credit bureau enquiries | 6 |
| Income and employment | 5 |
| Application timing and history | 5 |
| Loan terms | 4 |
| Social circle | 4 |
| Assets | 3 |
| External scores | 3 |
| ID and label | 2 |

Types: 57 numeric continuous, 36 binary flag, 12 numeric count, 11 nominal, 4 ordinal, 1 ID, 1 target.

The data has no repayment history, loan term, interest rate, loan purpose or application date. [DATA] A bank would also use bureau history and its own repayment records. [GENERAL] Those sit in the excluded tables. This means the three external scores carry much of the signal.

## 4. Key findings

1. **Class balance.** 14,895 defaults against 169,611 non-defaults, a ratio of 11.39 to 1. An approve-everyone rule gets 91.93% accuracy and catches no defaulter. Use AUC, Gini, KS and PR-AUC. The floor for PR-AUC is the default rate, 0.0807.
2. **The three `EXT_SOURCE` columns dominate.** Decile default rates fall from about 17% to 20% in the lowest decile to about 3% in the highest. Their Pearson correlations with `TARGET` are -0.18, -0.16 and -0.15. The next column, `DAYS_BIRTH`, is +0.08. Only 3 of 104 numeric columns exceed 0.10 in absolute value.
3. **Missingness is large and structured.** 67 of 122 columns have missing values, 57 above 5%, 41 above 50%. Only 2.78% of rows are complete. The 67 columns form 31 distinct missing patterns. Default rates differ between missing and present rows in every pattern above 5%. The gaps are +1 to +3 points, except `OCCUPATION_TYPE` at -2.2, which is mostly the pensioner effect. These are small to moderate gaps.
4. **Some missingness is structural.** `OWN_CAR_AGE` is missing for all non-owners. `OCCUPATION_TYPE` is missing for 99.99% of pensioners.
5. **The bureau block is nested inside `EXT_SOURCE_3`.** When the six enquiry columns are missing, `EXT_SOURCE_3` is missing in 100% of those rows.
6. **Correlation misses humps.** `AMT_ANNUITY` has a Spearman of -0.001 with `TARGET`, but its decile default rate rises from 7.25% to 10.00% and falls to 5.73%. Bins or trees see this. A straight line does not.
7. **Heavy redundancy.** 14 building stems come in three flavours with correlations of 0.965 or more. 19 columns are at least 99% one value. Several non-building pairs correlate above 0.8 (for example `AMT_CREDIT` and `AMT_GOODS_PRICE` at 0.987).
8. **`EXT_SOURCE_1` tracks age.** r = -0.60 with `DAYS_BIRTH`, and its missing share rises from 41.5% to 77.3% across age quintiles. It may act as an age proxy. Hypothesis.

## 5. Data quality issues

| Issue | Evidence [DATA] | Proposed handling (not decided) |
|---|---|---|
| `DAYS_EMPLOYED` placeholder 365243 | 33,225 rows (18.01%), all Pensioner or Unemployed | Replace with missing and add a flag |
| `ORGANIZATION_TYPE` = XNA | 33,225 rows, the same rows as the placeholder | Treat as the same fact, not a separate one |
| Other XNA and unknown labels | `CODE_GENDER` XNA 2 rows, `NAME_FAMILY_STATUS` Unknown 1 row, `FONDKAPREMONT_MODE` "not specified" 3,412 rows | Pool or mark as missing |
| Extreme `AMT_INCOME_TOTAL` | max 117,000,000, p99 472,500, 144 rows above 1,000,000 | Cap at p99.9 or use a log scale |
| Extreme counts | `OBS_30_CNT_SOCIAL_CIRCLE` max 348 (p99 10), `CNT_CHILDREN` max 19, bureau counts up to 27 | Cap or merge the upper tail |
| `OWN_CAR_AGE` spike | 1,992 rows at ages 64 and 65, one row at 63, none from 66 to 90. Cause unknown. | Needs your view |
| `AMT_GOODS_PRICE` clump | 15,614 rows (8.46%) equal 450,000, default rate 13.67% against 7.56% for the rest. Cause unknown. | Needs your view |
| Near-constant columns | 19 columns with a top value of 99% or more | Drop or pool |
| Rare categories | 67 category rows under 1% of rows, for example "Unemployed" 26.67% on 15 rows | Pool before binning |
| Natural missingness | 67 columns | See open question 4 |

No column name looks like an outcome. [DATA] Leakage suspicions below are hypotheses only.

## 6. Feature shortlist (proposal, 28 features)

Full table with one-line reasons: `section7_shortlist.md`. All 122 columns with status: `feature_shortlist.csv`.

| Group | Features |
|---|---|
| Loan terms | `AMT_CREDIT`, `AMT_ANNUITY`, `NAME_CONTRACT_TYPE` |
| Income and employment | `AMT_INCOME_TOTAL`, `DAYS_EMPLOYED`, `NAME_INCOME_TYPE`, `OCCUPATION_TYPE` |
| Demographics | `NAME_EDUCATION_TYPE`, `NAME_HOUSING_TYPE`, and two that need a ruling: `DAYS_BIRTH`, `NAME_FAMILY_STATUS` |
| Assets | `FLAG_OWN_CAR` |
| External scores | `EXT_SOURCE_1`, `EXT_SOURCE_2`, `EXT_SOURCE_3` |
| Region and address | `REGION_RATING_CLIENT_W_CITY`, `REGION_POPULATION_RELATIVE`, `REG_CITY_NOT_LIVE_CITY`, `REG_CITY_NOT_WORK_CITY` |
| Application timing and history | `DAYS_REGISTRATION`, `DAYS_ID_PUBLISH`, `DAYS_LAST_PHONE_CHANGE` |
| Contact | `FLAG_WORK_PHONE` |
| Bureau enquiries | `AMT_REQ_CREDIT_BUREAU_QRT`, `AMT_REQ_CREDIT_BUREAU_YEAR` |
| Building | `FLOORSMAX_AVG`, `LIVINGAREA_AVG`, `WALLSMATERIAL_MODE` |

- Highest correlation between two shortlisted numeric columns: 0.77 (`AMT_CREDIT` and `AMT_ANNUITY`). 17 of 28 are fully observed. 8 have natural missing above 5%.
- Excluded by default, but plausible if you rule otherwise: `CODE_GENDER`, `ORGANIZATION_TYPE`, `AMT_GOODS_PRICE`, `OWN_CAR_AGE`, `FLAG_DOCUMENT_3`, `FLAG_DOCUMENT_6`, `DEF_30_CNT_SOCIAL_CIRCLE`.
- The evidence behind each pick is one column at a time. It does not show what a column adds inside a model.

## 7. Corruption candidates (proposal)

Predictions were written before any corruption function or model existed. Details and falsifiers: `section8_corruption_candidates.md`.

| # | Target | Scenario | Predicted effect at 50% severity (guess) |
|---|---|---|---|
| 1 | `EXT_SOURCE_2` | A: MNAR missingness | Largest AUC drop (0.01 to 0.03). Premium stays above 0. |
| 2 | `AMT_INCOME_TOTAL` | A: MNAR missingness | Smallest drop (0.005 or less). Premium unchanged. |
| 3 | `TARGET` training labels | B: label lag | Random hiding is mild. Hiding that depends on loan term hurts the GBM more, and the premium interval may include 0 at 25% to 50%. |
| 4 | `AMT_CREDIT` and `AMT_ANNUITY` | C: scale drift | Drop of 0.005 to 0.02, similar for both models. |
| 5 | `DAYS_EMPLOYED` placeholder | C: schema drift | Drop of 0.01 or less. Pensioner flag offsets part of the error. |

Main prediction: complexity stops paying only under label hiding that depends on a feature. For the four feature-level candidates, I expect the premium interval to stay above 0.

## 8. Open questions

**Decisions that are yours** (not made here):
1. Shortlist (1.5): rule on `DAYS_BIRTH` and `NAME_FAMILY_STATUS` (in the proposal), `CODE_GENDER` (out), and the seven excluded options. Decide whether engineered ratios (payment-to-income, credit-to-income, implied term) are allowed.
2. Corruption targets (1.7): which of the five are in. Dropping #2 and #5 leaves one per scenario.
3. What severity means per scenario (share of rows, share of eligible rows, or size of the shift), and which splits are corrupted. For #5, 50% must mean 50% of placeholder rows, about 9% of all rows.
4. Natural missingness: leave as is or impute first. This sets what "0%" means.
5. Missing-value handling per model: scorecard missing bin and GBM native handling, or one shared imputation.
6. Class handling: no rebalancing is my hypothesis, but a bank scorecard needs calibrated PD. How the project handles this is open.

**Facts I could not establish**:
7. The cause of the `OWN_CAR_AGE` spike and the `AMT_GOODS_PRICE` clump at 450,000.
8. The source and timing of the `EXT_SOURCE` columns, and when the social-circle default counts were observed. If either holds post-origination information, results are inflated. Hypothesis.
9. The values of X and Y in the `TARGET` definition, and how it applies to revolving loans.

**Housekeeping**:
10. `dataset/` has 7 files, but one is `sample_submission.csv`, so there are 6 auxiliary tables.
11. This session wrote to `reports/eda/`. Earlier work (items 1.4 and 1.6) is in `docs/eda/`. The two are not merged. Which folder should hold the final reports?
12. Nothing from this session is committed.

## 9. Reproduce

```bash
python -m poetry run python -m src.data.run_eda
```

This runs eight steps in order and rebuilds every file in `reports/eda/` and `data/interim/split_indices.csv` in about two minutes. It needs `data/raw/application_train.csv` and `data/processed/train.csv`. I ran it from scratch at the end of the session and it finished without errors. Every step after the first reads `train.csv` only. The Q&A log is `qna_log.md` and is empty so far.

| Section | Notes | Script |
|---|---|---|
| 1 Integrity and split | `section1_integrity.md` | `src/data/integrity.py` |
| 2 Dataset | `section2_dataset.md`, `section2_facts.md` | `src/data/section2_facts.py` |
| 3 Feature catalog | `feature_catalog.csv`, `section3_features.md`, `section3_facts.md` | `src/data/feature_catalog.py` |
| 4 Target and imbalance | `section4_target.md` | `src/data/target_balance.py` |
| 5 Missingness | `section5_missingness.md`, `section5_facts.md`, two CSVs, three figures | `src/data/missingness_baseline.py` |
| 6 Univariate and bivariate | `section6_eda.md`, `section6_facts.md`, CSVs, five figures | `src/data/eda_section6.py` |
| 7 Shortlist | `section7_shortlist.md`, `feature_shortlist.csv` | `src/data/shortlist.py` |
| 8 Corruption candidates | `section8_corruption_candidates.md`, `section8_facts.md` | `src/data/corruption_candidates_facts.py` |
