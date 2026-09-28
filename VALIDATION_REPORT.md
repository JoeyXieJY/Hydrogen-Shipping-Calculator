# Validation report

## Verification completed

- `python -m pytest -q`: 24 passed.
- `python -m compileall -q .`: passed.
- Streamlit `AppTest`: no exceptions; 10 metrics, 5 dataframes and 8 expanders rendered.
- Headless Streamlit startup: server started successfully and was stopped after the smoke-test timeout.

## Files changed

- `app.py`: complete interface update, editable confirmed assumptions, result tables/charts, source table, CSV downloads and OAT sensitivity analysis.
- `model.py`: new route, mass-balance, cost, cracking, emissions and sensitivity calculations.
- `model_data.json`: authoritative defaults, source metadata, sensitivity ranges and new regression fixtures.
- `test_model.py`: 24 engineering-invariant and regression tests.
- `README.md`, `CODEX_STEPS.md`, `STAGE2_CHANGES.md`: operation and audit documentation.
- `requirements.txt`: adds pytest as a test dependency.

## Important assumptions still requiring project-specific confirmation

- Original workbook CAPEX, OPEX, labour, port, exchange-rate and project-finance values remain legacy assumptions whose source year was not verified.
- Tokyo import-terminal electricity intensity uses the export value as an editable proxy, not a measured Tokyo value.
- Ammonia-engine N2O is a scenario value, not an established industry default.
- BOG is 100% controlled/utilised by default; users can change the vented share.
- Hydrogen leakage climate impact is supplementary and is excluded from carbon cost by default.
- Terminal and cracking sensitivity intervals are scenario ranges, not statistical confidence intervals.

## Regression results under default assumptions

| Carrier | Shipping cost (A$/kg H2-eq) | Landed cost (A$/kg H2) | Delivered H2 (kg/year) | Transport-chain emissions (t CO2e/year) |
|---|---:|---:|---:|---:|
| Ammonia | 0.355171 | 0.978345 | 243,780,143.99 | 862,548.97 |
| Hydrogen | 0.791743 | 0.791743 | 182,153,657.02 | 131,645.53 |

These values verify deterministic implementation of the selected assumptions. They are not a claim that the underlying project assumptions have been independently validated.

