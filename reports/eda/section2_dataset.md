# Section 2: what is this dataset?

Evidence labels: [DATA] verified by code in this session (numbers in `section2_facts.md`, train split only), [DOC] taken from `HomeCredit_columns_description.csv`, [GENERAL] general domain knowledge, not verified against a source in this session.

## Origin

- Home Credit is a consumer finance lender. It is known for lending to people with short or no credit history, in Eastern Europe and Asia. [GENERAL]
- The Kaggle competition "Home Credit Default Risk" asked teams to predict which applicants would have repayment problems. The files are the application table (train and test) and six auxiliary tables. [GENERAL]
- The description file documents 7 tables in total: the application table plus 6 auxiliary ones (bureau, bureau_balance, previous_application, POS_CASH_balance, credit_card_balance, installments_payments). [DOC]
- Country and currency are not stated in the data or the description file. [DATA] Do not assume a currency.

## Unit of observation

- One row is one loan in the sample. The description file says SK_ID_CURR is the "ID of loan in our sample". [DOC]
- In train there are 184,506 rows and 184,506 unique SK_ID_CURR. [DATA]
- Correction to a common assumption: SK_ID_CURR identifies a loan, not a person. There is no client ID in this table, so we cannot tell whether one person appears twice. Not verified.
- Every column describes what was known at application time, plus the label.

## Target

- Exact definition from the description file [DOC]: "Target variable (1 - client with payment difficulties: he/she had late payment more than X days on at least one of the first Y installments of the loan in our sample, 0 - all other cases)".
- X and Y are not given in the file. Their values are not verified.
- 1 = at least one late payment beyond X days in the first Y installments. 0 = everything else. [DOC]
- Train: 14,895 rows are 1 (8.07%), 169,611 rows are 0 (91.93%). [DATA]
- What TARGET does not tell us:
  - It is not a final write-off or a loss. A client can be late once, then pay in full, and still be 1. [DOC, from the definition]
  - It only looks at the first Y installments. Later problems are labelled 0. [DOC]
  - It carries no loss amount, so it says nothing about severity. [DOC]
  - Revolving loans have no fixed installments, so how the label applies to them is not verified. [DATA] shows the rate differs by contract type: cash 8.33% (n=166,883), revolving 5.62% (n=17,623).

## Population and sampling caveats

| Point | Label |
|---|---|
| Every row has an outcome, so every row is a loan that was granted. Rejected applicants are not in this table. Their absence is inferred, not verified. | [GENERAL] |
| No approval or rejection status column exists in the application table. | [DATA] |
| Because only approved loans are seen, a model trained here learns to rank applicants who already passed Home Credit's own screen. This is called selection bias or reject inference problem. | [GENERAL] |
| The mix is mostly cash loans (166,883 rows, 90.45%) and some revolving loans (17,623 rows, 9.55%). | [DATA] |
| Gender: 121,426 F (65.81%), 63,078 M (34.19%), 2 coded XNA. | [DATA] |
| Age: min 21.0, median 43.1, max 69.0 years. Pensioners are 33,218 rows (18.00%). | [DATA] |
| Income: median 148,500, mean 169,223 (currency unknown). The mean sits above the median, so the right tail is long. | [DATA] |
| Education: secondary 131,154 (71.08%), higher 44,721 (24.24%). | [DATA] |
| Sampling method and any subsampling by Home Credit are not described. | not verified |
| No calendar date, so we cannot check for changes in the economy or in policy over time. | [DATA] |

## Real-world usage

- This is the kind of data used for an application scorecard: estimate the probability of default (PD) for a new applicant at origination. [GENERAL]
- A bank uses the score to approve or decline, set a limit or price, and route borderline cases to manual review. [GENERAL]
- Regulators and risk teams expect scorecards to be explainable. That is why a WOE-binned logistic regression is the standard baseline. [GENERAL]
- The competition asked only for ranking quality, not for calibrated probabilities or approval cutoffs. [GENERAL]

## How it is used in this project

- Question: at what level of data degradation does a complex model (XGBoost) stop beating a simple scorecard, and what happens to explainability.
- The application table has no calendar dates. [DATA] Only offsets such as DAYS_BIRTH, relative to the application day, plus weekday and hour of application.
- That is a design choice that helps here, not a flaw:
  - We can build a clean random train, val, test split. A time-based split is impossible, so there is no hidden drift between the splits.
  - Any drift we study is drift we inject ourselves in Scenario C. We know the cause and the size.
  - A cost: we cannot test how well a model holds up over real time. That belongs in the non-goals.

## The 6 auxiliary tables (excluded)

- bureau and bureau_balance: the client's past credits at other lenders and their monthly status. previous_application: earlier applications at Home Credit, including refusals. POS_CASH_balance, credit_card_balance and installments_payments: monthly behaviour on earlier Home Credit products. [DOC]
- They would add repayment history, which is the strongest kind of information in real scorecards, and they would also reveal rejected prior applications.
- They are excluded from this project. They are not loaded in any step.
- Small repo note: `dataset/` holds 7 files, but one is `sample_submission.csv`, which is a Kaggle submission template and not a data table. So there are 6 auxiliary tables, not 7. [DATA from directory listing]
