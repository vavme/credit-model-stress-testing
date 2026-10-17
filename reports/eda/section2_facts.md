# Section 2 facts (train split only)

## Documentation file: rows per table

| Table | Documented columns |
|---|---|
| application_{train|test}.csv | 122 |
| previous_application.csv | 38 |
| credit_card_balance.csv | 23 |
| bureau.csv | 17 |
| POS_CASH_balance.csv | 8 |
| installments_payments.csv | 8 |
| bureau_balance.csv | 3 |

TARGET description (quoted from file): Target variable (1 - client with payment difficulties: he/she had late payment more than X days on at least one of the first Y installments of the loan in our sample, 0 - all other cases)

## Unit of observation

- Rows: 184,506. Unique SK_ID_CURR: 184,506.
- Columns with calendar-style names (date, month, timestamp): none.
- DAYS_* columns: ['DAYS_BIRTH', 'DAYS_EMPLOYED', 'DAYS_REGISTRATION', 'DAYS_ID_PUBLISH', 'DAYS_LAST_PHONE_CHANGE']. Only WEEKDAY_APPR_PROCESS_START and HOUR_APPR_PROCESS_START describe application timing (day of week, hour).
- Application weekday counts: {'TUESDAY': 32381, 'WEDNESDAY': 30897, 'MONDAY': 30659, 'FRIDAY': 30364, 'THURSDAY': 30218, 'SATURDAY': 20218, 'SUNDAY': 9769}

## Who the borrowers are (train)

- Age in years: min 21.0, median 43.1, max 69.0.
- AMT_INCOME_TOTAL: median 148,500, mean 169,223. Currency is not stated in the data or the description file.
- AMT_CREDIT: median 514,822.
- NAME_CONTRACT_TYPE: Cash loans 166,883 (90.45%); Revolving loans 17,623 (9.55%)
- CODE_GENDER: F 121,426 (65.81%); M 63,078 (34.19%); XNA 2 (0.00%)
- NAME_INCOME_TYPE: Working 95,140 (51.56%); Commercial associate 42,989 (23.30%); Pensioner 33,218 (18.00%); State servant 13,127 (7.11%); Unemployed 15 (0.01%); Student 8 (0.00%); Businessman 7 (0.00%); Maternity leave 2 (0.00%)
- NAME_EDUCATION_TYPE: Secondary / secondary special 131,154 (71.08%); Higher education 44,721 (24.24%); Incomplete higher 6,270 (3.40%); Lower secondary 2,272 (1.23%); Academic degree 89 (0.05%)
- NAME_FAMILY_STATUS: Married 117,757 (63.82%); Single / not married 27,350 (14.82%); Civil marriage 17,908 (9.71%); Separated 11,863 (6.43%); Widow 9,627 (5.22%); Unknown 1 (0.00%)
- FLAG_OWN_CAR: N 121,848 (66.04%); Y 62,658 (33.96%)
- FLAG_OWN_REALTY: Y 128,053 (69.40%); N 56,453 (30.60%)

## TARGET (train)

- TARGET = 1: 14,895 (8.07%); TARGET = 0: 169,611 (91.93%).
- Default rate by NAME_CONTRACT_TYPE (train): Cash loans 8.33% (n=166,883); Revolving loans 5.62% (n=17,623)
- Columns that look like a loan outcome or approval status (STATUS, APPROVED, REFUSED, WRITE): ['NAME_FAMILY_STATUS']

