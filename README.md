# Credit Risk Under Data Quality Degradation

Testing where model complexity stops paying for itself as data quality degrades, and what happens to explainability along the way.

## Hypothesis

I want to find the point where XGBoost stops beating a simple WOE-based credit scorecard by a margin that actually matters, as the input data gets worse. I'll corrupt the Home Credit dataset in three ways that mirror real banking data problems: values going missing in a way tied to risk, loan labels being recorded before the loan's true outcome is known, and a feature's scale or structure quietly changing underneath the model, each at increasing severity. My guess is the accuracy gap shrinks gradually with missingness and label immaturity, since WOE's coarse bins and the model's own capacity constraints absorb small, spread-out errors, but drops sharply once schema or scale drift hits, since that corruption realistically corrupts an entire feature at once rather than a growing share of rows. I'm defining "stop paying for itself" as the point where the bootstrapped confidence interval on that gap first includes zero. I don't have a strong prediction for whether label immaturity or schema drift causes more total damage, that's genuinely one of the things the experiment needs to answer. I also expect the complex model's SHAP-based explanations to get unstable before its accuracy visibly drops, which matters because a bank needs a defensible reason for every credit decision, not just an accurate one.

## Non-goals

- Not competing for Kaggle leaderboard AUC: success is honest offline evaluation on our own held-out split, not a public score (`application_test.csv` is unlabeled and out of scope entirely).
- Not using all 6 auxiliary tables: sticking to `application_train.csv` and a 25-40 feature shortlist from it.
- Not running a hyperparameter tuning marathon: a reasonably-tuned GBM is enough; the contribution is the corruption/complexity trade-off, not marginal AUC.
- Not measuring or optimizing training time, compute, or infrastructure cost: at ~300K rows, logistic regression and a GBM both train in under a minute. Not a meaningful axis at this scale.
- Not using a neural network as the complex model, and not testing data-hunger/sample-efficiency: the complex model is a GBM (XGBoost).
- Not quantifying real implementation, governance/validation, or monitoring cost in dollars or hours: these are named as motivation for why complexity isn't free, not something this project measures directly.
- Not optimizing against a specific bank's business objective (a target approval rate or bad rate cutoff): the comparison is judged on overall discrimination (AUC/Gini/KS).
- Not declaring a fixed accuracy threshold (e.g. "must beat by 5 points") as the definition of "worth it": materiality is read off the bootstrapped confidence interval on the complexity premium at each corruption severity level.
- Not building a production-serving or real-time scoring pipeline: this stays a research/offline comparison, not a deployable service.
- Not running a formal fairness or disparate-impact audit: a real bank deployment would need this, but it's a distinct project on its own and out of scope here.
- Not benchmarking other complex-model families (LightGBM, CatBoost, etc.): XGBoost is the one complex model, fixed by design, not chosen through a bake-off.

## Data

[Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk) (Kaggle), `application_train.csv` only (~307K rows, ~122 columns, ~8% default rate). `application_test.csv` has no public labels and is not used for evaluation.

Kaggle competition data can't be redistributed, so raw CSVs are not committed to this repo (`data/` is gitignored). Fetch it yourself:

```bash
poetry run python -m src.data.download_home_credit
```

This requires a Kaggle API token at `~/.kaggle/kaggle.json` and accepting the competition rules on kaggle.com first; see the docstring in that script for the exact steps.

There's no real calendar date in this dataset (`DAYS_BIRTH`, `DAYS_EMPLOYED`, etc. are relative offsets). That's a deliberate feature, not a limitation: this is a controlled experiment where the independent variable is injected corruption severity, and a real calendar axis would confound results with actual economic-cycle effects.

## How to reproduce

```bash
# 1. Install dependencies (Poetry)
poetry install

# 2. Fetch the data (see "Data" above; requires a Kaggle API token)
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
configs/       experiment configs, YAML, parsed into a dataclass (see docs/decisions/0.8-config-schema.md)
```

## Development process

This project was built with help from Claude Code for implementation work, alongside a separate conversation with Claude where the actual research decisions got made: the hypothesis, the corruption scenario design, bin-edge review, and anything else that needed real judgment. A local `CLAUDE.md` file enforces that split during development, spelling out which decisions are mine and which are safe to delegate. It isn't committed here because it's tooling setup, not project content, not because the process is a secret.

## Status

Phase 0 (Scope Lock & Setup) is complete; currently on Phase 1 (Data Acquisition & EDA).
