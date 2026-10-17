# Section 8: corruption target candidates (proposal)

Written 2026-10-17, **before any corruption function or model exists**. This is a proposal. Picking the targets is tracker item 1.7, which is Vav's decision. Nothing here is implemented. Clean-state numbers are from the train split (`section8_facts.md`, from `src/data/corruption_candidates_facts.py`). Labels: [DATA] verified by code, [GENERAL] domain knowledge not verified here, "guess" = my prediction, not a result.

Terms: the **premium** is GBM AUC minus scorecard AUC. "Complexity stops paying" means the bootstrapped interval on the premium includes 0 (the project's own rule). The **clean premium** is the premium at 0% severity.

## Proposal at a glance

| # | Target | Scenario | Banking failure mode | Predicted damage at 50% (rank) |
|---|---|---|---|---|
| 1 | EXT_SOURCE_2 | A: MNAR missingness | External bureau score is not returned for applicants it cannot score | 1 (largest) |
| 2 | AMT_INCOME_TOTAL | A: MNAR missingness | Self-reported income left blank, more often by some income levels | 5 (smallest) |
| 3 | TARGET (training labels) | B: label lag | Late defaults not yet recorded when the training set is cut | 2 |
| 4 | AMT_CREDIT + AMT_ANNUITY | C: scale drift | Amount fields change units or are re-based between systems | 3 |
| 5 | DAYS_EMPLOYED placeholder | C: schema drift | "Not employed" is re-encoded by a source system | 4 |

Assumptions behind all predictions (each is an open question for Vav, see the end): A is applied to all splits. B is applied to training labels only and models are scored against clean labels. C is applied to the held-out split only, with models fitted on clean train. Severity means share of eligible rows affected.

My expectation for the clean state [GENERAL, not verified here]: the GBM beats the WOE scorecard by a small positive margin, roughly +0.01 to +0.03 AUC, with an interval that excludes 0. Every prediction below is relative to that.

---

## 1. EXT_SOURCE_2 missing not at random (Scenario A)

**Why it is realistic.** Scores from an outside bureau are missing when the bureau has no file or the call fails. Thin-file applicants are both harder to score and, plausibly, riskier. So missingness depends on the value itself. [GENERAL]

**Clean state [DATA].**
- Missing in 413 rows (0.22%), so almost no natural missing to mix with injected missing.
- Strongest complete column: Spearman -0.147. Decile default rate falls from 18.3% to 2.8%.
- The other two scores cannot stand in for it: r = +0.213 with EXT_SOURCE_1 and +0.108 with EXT_SOURCE_3.
- Only 65,639 rows (35.58%) have all three scores. Natural missing in the other two is already large (Section 5).

**Mechanism family to implement later (idea only).** Probability of missing rises as the score falls, scaled so the share of rows hidden equals the severity.

**Predictions (guesses).**
1. Both models lose AUC at every step. At 10% the drop is under 0.005, at 25% it is 0.005 to 0.015, at 50% it is 0.01 to 0.03.
2. The drop is smaller than it would be if the same rows were hidden at random. Under MNAR the "is missing" marker carries risk information, and both models can use it (scorecard missing bin, GBM native missing branch).
3. The premium stays positive with an interval that excludes 0 at all four severities. I expect no crossover here. Confidence: medium-low.
4. Explainability: EXT_SOURCE_2 drops in global importance in both models. The scorecard shows a large-points "missing" bin for it. GBM importance shifts partly to EXT_SOURCE_1 and EXT_SOURCE_3, but only partly, given the low correlations.

**What would prove me wrong.** The premium interval includes 0 at 25% or below. Or the scorecard loses less AUC than the GBM.

## 2. AMT_INCOME_TOTAL missing not at random (Scenario A, low-signal contrast)

**Why it is realistic.** Income on an application is often self-reported and left blank, and who leaves it blank is tied to the amount. [GENERAL]

**Clean state [DATA].**
- Fully observed (0 missing). Median 148,500, p99 472,500, max 117,000,000.
- Weak alone: Spearman -0.019. Decile default rates are flat around 8% to 9% until the top two deciles (7.0% and 6.1%). Range 2.69 pp.
- It correlates with the loan fields (Spearman +0.41 with AMT_CREDIT, +0.48 with AMT_ANNUITY), so its information may come through ratios.

**Predictions (guesses).**
1. At 50% the AUC drop is 0.005 or less for both models, and the gap between the models is inside the noise.
2. The premium is unchanged. No crossover. Confidence: low-medium.
3. Purpose in the design: it shows that how much a feature matters can dominate which model is used. If it fails, that is informative too.

**What would prove me wrong.** A drop above 0.01 at 50%. The most likely reason would be an interaction with the loan amounts that the GBM exploits and the scorecard cannot, in which case the GBM drop would be larger than the scorecard drop. This is where I am least sure.

## 3. TARGET labels: late defaults not yet recorded (Scenario B)

**Why it is realistic.** A training set is cut at a date. Loans that will default later are recorded as 0. This hits long-tenor loans hardest, because their missed payments appear later. [GENERAL] The data has no dates, so the lag must be simulated.

**Clean state [DATA].** 14,895 defaults (8.07%). Arithmetic if a share of defaults is hidden:

| Defaults hidden | Defaults left | Default rate | Defaults in a 1% bin | Ratio 0 : 1 |
|---|---|---|---|---|
| 0% | 14,895 | 8.07% | 149 | 11.4 : 1 |
| 10% | 13,406 | 7.27% | 134 | 12.8 : 1 |
| 25% | 11,171 | 6.05% | 112 | 15.5 : 1 |
| 50% | 7,448 | 4.04% | 74 | 23.8 : 1 |

**Two mechanisms, and the difference matters.**
- *B-random:* each default is hidden with the same probability. Reasoning: if the chance of being recorded as 1 is scaled by a constant, the learned risk ordering is unchanged in expectation. Any class-conditional noise that does not depend on the features keeps the ranking and mostly shrinks the effective number of defaults. So this is a benign control.
- *B-segment:* the hiding probability rises with a feature such as implied term (AMT_CREDIT / AMT_ANNUITY, median 20.0, p10 to p90 10.5 to 34.1 [DATA], a hypothesis for the number of instalments) or AMT_CREDIT. Then the models learn that long-term loans are safer than they are. This is the realistic and damaging case.

**Predictions (guesses), evaluated on clean labels.**
1. B-random: the AUC drop is small for both, at most 0.01 at 50%, and the premium interval stays above 0. The GBM may lose slightly more through overfitting.
2. B-segment: both models lose AUC, the GBM more than the scorecard, because it can learn the segment distortion more sharply through interactions of the two loan fields. The premium shrinks steadily with severity and its interval first includes 0 at 25% to 50%. Confidence: low-medium.
3. This is the only candidate where I expect complexity to stop paying within the severity grid.
4. Explainability: the GBM's SHAP ranking reshuffles among weak columns. The scorecard's loan-amount bins flip direction for large, long loans, which is visible and explainable.

**What would prove me wrong.** B-random hurts more than B-segment, or the premium stays clearly above 0 at 50% under B-segment.

## 4. AMT_CREDIT and AMT_ANNUITY scale drift (Scenario C)

**Why it is realistic.** Amount fields change after a currency redenomination, an inflation step, or a system migration that re-bases amounts. [GENERAL]

**Clean state [DATA].**
- Medians: AMT_CREDIT 514,822; AMT_ANNUITY 24,930. r = +0.770 between them. Both complete or nearly so.
- Both are hump-shaped against default. AMT_CREDIT deciles run 6.8%, 7.9%, 8.0%, 10.1%, 9.6%, 10.4%, 8.5%, 7.1%, 6.8%, 5.4%. A rank correlation near 0 hides this.
- Implied term is unchanged if both amounts are scaled by the same factor. Payment-to-income changes if income is not scaled.

**Mechanism family (idea only).** Multiply both amounts by a fixed factor in the affected rows of the held-out split. The factor is a design choice.

**Predictions (guesses).**
1. AUC drops for both models. At 50% of rows the drop is 0.005 to 0.02.
2. The two models lose a similar amount, and the difference is inside the noise. Both rely on cut points that learned the old scale: WOE bins in the scorecard, tree splits in the GBM.
3. The premium is unchanged and the interval stays above 0. No crossover. Confidence: low.
4. Explainability: no change in the fitted model's explanations, because the model is fixed and only the inputs move. The change appears in the contribution of each row.

**What would prove me wrong.** The GBM drop is clearly larger, which would mean its fine splits on the old scale are more brittle than wide WOE bins.

## 5. DAYS_EMPLOYED placeholder re-encoded (Scenario C, schema drift)

**Why it is realistic.** A source system changes how "no current employer" is encoded, for example from a placeholder to 0 or a blank. [GENERAL]

**Clean state [DATA].**
- Placeholder 365243 in 33,225 rows (18.01%), default rate 5.41%, against 8.66% for the rest.
- All 33,225 are Pensioner (33,210) or Unemployed (15). Only 8 Pensioner or Unemployed rows are not placeholder. So NAME_INCOME_TYPE carries almost the same fact.
- If the placeholder became 0 days, those rows would land with the shortest real tenures (-333 to 0 days, n = 15,125), whose default rate is 11.13%.

**Predictions (guesses).**
1. At 50% of the placeholder rows recoded, the AUC drop is 0.01 or less for both models. NAME_INCOME_TYPE partly cancels the error.
2. The scorecard drops a little more than the GBM, because its DAYS_EMPLOYED contribution jumps from a low-risk bin to the highest-risk bin and adds up with the rest. Confidence: low.
3. The premium is unchanged within noise. No crossover.
4. Explainability: the scorecard's DAYS_EMPLOYED points become visibly wrong for pensioners, while the GBM's explanation for those rows is spread across more features.

**What would prove me wrong.** A drop above 0.02, which would mean the pensioner flag does not offset the recoding.

**Design catch.** The placeholder covers only 18.01% of rows, so "50% severity" cannot mean 50% of all rows. It must mean 50% of the placeholder rows, which is about 9% of all rows. The same issue applies to any candidate defined on a subgroup.

---

## Cross-candidate predictions (guesses)

1. Damage to AUC at 50%, largest to smallest: #1 EXT_SOURCE_2, #3 B-segment, #4 amounts, #5 DAYS_EMPLOYED, #2 income. Confidence: low-medium. The ordering follows signal strength and how much of that signal is still available elsewhere.
2. Complexity stops paying (premium interval includes 0) only under #3 B-segment, and only at 25% to 50%. Feature-level corruption narrows the premium at most. If this is right, the answer to the project question depends on the kind of degradation, not just its level. If it is wrong, the prediction that the interval stays above 0 for all feature candidates fails first.
3. Explainability: the GBM's global importance ordering will move more than the scorecard's points under every candidate. This is the other half of the hypothesis and is untested.

## Not proposed, and why

- **Building block (47 columns):** already 47 to 70% missing, so Scenario A has no clean baseline there. Could model a whole-source outage later. Not a good first test.
- **EXT_SOURCE_1 and EXT_SOURCE_3:** 56.39% and 19.82% natural missing, nested with other blocks (Section 5). Messy baseline.
- **Bureau enquiry block (6 columns):** weak signal (best decile range 1.68 pp) and 13.48% natural missing. Useful as a negative control if you want one.
- **OCCUPATION_TYPE:** 31.38% missing, mostly structural.

## Questions for you

These change how the predictions are scored, so they should be settled before any experiment.
1. Which of the five are in? Item 1.7 is yours. Dropping #2 and #5 would leave three, one per scenario.
2. What does severity mean per scenario: share of rows, share of eligible rows, or size of the shift? For #5 and the placeholder it must be the eligible rows.
3. Which splits are corrupted: A on all splits, B on train labels only (scored against clean labels), C on the held-out split only? I assumed so above.
4. Natural missingness (Section 5): leave as is, or impute first? It changes what 0% means for #1 and #2.
5. How should each model treat missing values: a scorecard missing bin and GBM native handling, or one shared imputation? This can change the premium by itself.
