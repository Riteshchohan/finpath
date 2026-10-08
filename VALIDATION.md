# Delivery validation — 8 October 2026

## Completed

- 15 automated tests passed in base mode (pytest).
- Live HTTP test passed across both running servers: Flask → FastAPI → SQLite.
- Created an account, signed in, uploaded a synthetic six-month statement, reviewed and confirmed 67 transactions, and created a savings goal.
- Verified six complete historical months, goal milestones ending at the target, a purchase-budget result, local chatbot response, original-file download, and logout.
- Tested account isolation for files and goals, overlap rejection, import date validation, hashed session revocation, encrypted original bytes, transfer exclusion, multiple-goal budgeting, and CSRF rejection.
- Tested CSV, a generated DOCX table, and a generated text-PDF table. Arbitrary bank layouts still require review.
- Python compilation and JavaScript syntax checks passed.
- Chronos adapter calling convention and returned tensor layout were checked with an offline contract test and the official implementation.

## Not verified here

- Real Hugging Face weights were not downloaded or executed. Install the optional ML dependencies and run `download_models.py` to enable them. Base forecasting/category fallbacks work without these weights.
- Live Groq output was not tested because no API key was supplied. The consent boundary was tested without making external requests.
- Browser rendering and interactive UI automation were not completed: the Chromium download returned an invalid archive in this environment. The complete HTTP workflow and JavaScript syntax were verified, but that is not a substitute for browser QA.
- Predictive accuracy, anomaly precision/recall, and goal-success calibration have not been measured on real financial data. No performance percentage is claimed.
- No public deployment, security audit, or bank API integration was performed.

## Reproduce

```bash
python -m pytest -q
python tests/smoke_live.py
```

The smoke test starts temporary local servers on ports 5000 and 8000, uses synthetic data in a temporary directory, then stops them. Close any running FinPath instance before running it. The optional PDF fixture uses `reportlab`; install it if you want that test to run instead of skip.

For manual browser verification, create an account, upload the included sample, inspect/edit the review table, import, create/update/delete a goal, edit transaction categories, use Purchase check, ask the assistant a question, and test a narrow browser window. Check that no real documents or credentials enter a demonstration account.
