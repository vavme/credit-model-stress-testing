# Credit Risk Under Data Quality Degradation

Testing where model complexity stops paying for itself as data quality degrades, and what happens to explainability along the way.

## Hypothesis

_TBD — Phase 0.1, in progress. Pin the final 3-5 sentence hypothesis here before starting Phase 1._

## Non-goals

- Not competing for Kaggle leaderboard AUC — success is honest offline evaluation on our own held-out split, not a public score (`application_test.csv` is unlabeled and out of scope entirely).
- Not using all 6 auxiliary tables — sticking to `application_train.csv` and a 25-40 feature shortlist from it.
- Not running a hyperparameter tuning marathon — a reasonably-tuned GBM is enough; the contribution is the corruption/complexity trade-off, not marginal AUC.
- Not measuring or optimizing training time, compute, or infrastructure cost — at ~300K rows, logistic regression and a GBM both train in under a minute. Not a meaningful axis at this scale.
- Not using a neural network as the complex model, and not testing data-hunger/sample-efficiency — the complex model is a GBM (XGBoost).
- Not quantifying real implementation, governance/validation, or monitoring cost in dollars or hours — these are named as motivation for why complexity isn't free, not something this project measures directly.
- Not optimizing against a specific bank's business objective (a target approval rate or bad rate cutoff) — the comparison is judged on overall discrimination (AUC/Gini/KS).
- Not declaring a fixed accuracy threshold (e.g. "must beat by 5 points") as the definition of "worth it" — materiality is read off the bootstrapped confidence interval on the complexity premium at each corruption severity level.

## Data

[Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk) (Kaggle), `application_train.csv` only (~307K rows, ~122 columns, ~8% default rate). `application_test.csv` has no public labels and is not used for evaluation.

Kaggle competition data can't be redistributed, so raw CSVs are not committed to this repo (`data/` is gitignored). Fetch it yourself:

```bash
poetry run python -m src.data.download_home_credit
```

This requires a Kaggle API token at `~/.kaggle/kaggle.json` and accepting the competition rules on kaggle.com first — see the docstring in that script for the exact steps.

There's no real calendar date in this dataset (`DAYS_BIRTH`, `DAYS_EMPLOYED`, etc. are relative offsets). That's a deliberate feature, not a limitation: this is a controlled experiment where the independent variable is injected corruption severity, and a real calendar axis would confound results with actual economic-cycle effects.

## How to reproduce

```bash
# 1. Install dependencies (Poetry)
poetry install

# 2. Fetch the data (see "Data" above — requires a Kaggle API token)
poetry run python -m src.data.download_home_credit

# 3. Confirm the scaffold is sound
poetry run pytest

# 4. Work through notebooks/ and src/ per the phase backlog
```

## Repo structure

```
src/
  data/        data acquisition + the one stratified 60/20/20 split
  features/    feature shortlist + WOE/IV transformation
  corruption/  the three corruption scenarios (Phase 3, pure & seeded)
  models/      WOE/logistic regression baseline + GBM complex model
  eval/        metrics, bootstrapped CIs, the flat results table
  explain/     SHAP + coefficient-based explanations, stability checks
notebooks/     exploratory work
tests/         pytest suite
configs/       experiment configs (schema still TBD — see 0.8)
```

## Status

Tracked phase-by-phase in the [execution tracker](https://claude.ai/code/artifact/7e1e5876-5602-419c-808e-30b895829bcf). Currently on Phase 0 (Scope Lock & Setup).
