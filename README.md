# FinPath — personal finance website

A runnable **Flask website + FastAPI backend + SQLite** project. It supports statement upload and review, inflow/outflow analysis, unusual-transaction flags, goal roadmaps, purchase checks, and a budget assistant. Designed for a local project demonstration and further development. Not deployed or independently audited for public financial-service use.

## Quick start (Windows / VS Code)

Use Python 3.11 or 3.12. Extract the ZIP and open the `finpath` folder in VS Code. In its terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py
```

Open **http://127.0.0.1:5000** in your browser. Create your own account using a password of at least 10 characters. No shared admin account or hard-coded credentials are included. FastAPI documentation: http://127.0.0.1:8000/docs . Ctrl+C stops both servers.

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python run.py
```

If ports 5000 or 8000 are in use, stop the existing application using them. Always start from this folder with `run.py`. Base mode needs no API key or GPU and runs without network access after dependency installation.

## Try the website

1. Create an account and sign in.
2. Upload `samples/sample.csv`. For the included sample use **2026-04-01 to 2026-09-30**. To regenerate dates for your current month, run `python samples/make_sample.py`; it prints the new period.
3. Review all rows, category suggestions, amount signs, and essential flags; click **Confirm & import**.
4. Add a goal such as a ₹80,000 laptop, ₹10,000 already saved, deadline twelve months ahead.
5. Inspect the monthly milestones, discretionary spending budget, recurring payments, and unusual expenses.
6. Use **Purchase check**, supplying cash genuinely left after bills, goal savings, and the buffer.
7. Ask the budget assistant to explain your budget or anomalies.

Sample transactions are synthetic. The website starts empty; they are never silently added to a real account.

## Hugging Face models

Two real model adapters are included; model weights are **not bundled** in this ZIP:

| Component | Model / method | Purpose |
|---|---|---|
| Cash-flow forecast | `amazon/chronos-bolt-tiny` | Next-month inflow and outflow quantile forecasts, run locally on CPU |
| Category suggestions | `sentence-transformers/all-MiniLM-L6-v2` | Description similarity to category labels, combined with keyword rules |
| Unusual amounts | scikit-learn Isolation Forest | Fit to this user's inflows and outflows separately; descriptive outlier flags |
| Goal planner | Explicit arithmetic | Savings contributions, milestones, shared spending limits and shortfalls |

MiniLM is a general text embedding model, not a trained bank-transaction classifier. Its suggestions require review. Isolation Forest is fitted locally; it is not presented as a pretrained Hugging Face fraud detector. No pretrained model can guarantee a personal financial goal will be achieved.

Enable Hugging Face inference:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
.\.venv\Scripts\python.exe download_models.py
```

Then change `.env` and restart:

```dotenv
ENABLE_HF=1
HF_LOCAL_ONLY=1
```

The one-time download needs internet access to Hugging Face. CPU inference needs enough RAM for PyTorch and both models; allow several GB of free disk space for dependencies. No NVIDIA GPU is required. Model files are cached by Hugging Face outside the project. Inputs stay local; downloading weights does not upload statements. If a model fails to load, the UI explicitly identifies the fallback.

Forecasting requires at least three **consecutive complete** statement months for Chronos. More history is preferable. In base mode or with limited history, it uses the historical monthly median; conservative income is the 25th percentile. With Chronos, conservative income is the smaller of its 10th-percentile forecast and the historical 25th percentile. These quantiles are planning inputs, not calibrated goal-success probabilities. The planner assumes this monthly baseline continues until each deadline; it recalculates with new statements. It does not model investment returns or inflation.

## Optional free-tier AI chatbot

The default **local assistant is rule-based**, uses computed budgets and needs no API. For a conversational model, create your own Groq API key and set:

```dotenv
CHAT_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Groq's official documentation lists a rate-limited free plan; availability, models and limits may change. Check your account's current limits. No unlimited free API is promised. The website requires the user's consent checkbox for each external-chat request. It sends the question and aggregate budget numbers, not statement files, account email, merchant descriptions or goal names. Anything the user types into their question is still transmitted, so the UI asks them to avoid sensitive information. The key stays on the backend. API outages or exhausted quota fall back to the local assistant. Generated answers do not modify goals, transactions, or calculated budgets.

## How the goal roadmap works

For each goal:

```text
remaining = max(0, target - saved)
daily contribution = remaining / days until deadline
monthly equivalent = daily contribution × 30.4375
```

All goals' monthly equivalents are added before calculating discretionary spending:

```text
monthly discretionary limit = max(0,
  conservative monthly inflow
  - median essential monthly spending
  - 10% income buffer
  - sum of all goal contributions)

remaining month budget = max(0,
  monthly discretionary limit - recorded discretionary spending this month)
```

Roadmap milestones show the cumulative savings required at each month-end and the deadline. Already saved money must be allocated to just one goal. This is a budget feasibility estimate, not a guarantee. A deficit is shown as a shortfall. All transfers are excluded from income/spend calculations; loans, refunds and exceptional credits should be reviewed because cash inflow is not necessarily recurring income. Essential categories are editable.

The purchase checker compares an amount against both remaining discretionary budget and user-declared cash after reservations. It does not access live balances, reserve money, execute payments, or know about unrecorded purchases. Update statements and available cash before relying on it. It refuses to endorse spending when history is missing or more than 45 days old.

## Statement formats and storage

- Supported uploads: text-based **PDF**, **DOCX** (Word), and **CSV**. Save legacy `.doc` files as `.docx` first. Password-protected PDFs must be unlocked locally first. Scanned image PDFs require OCR outside this release; the app does not silently invent transactions.
- Best-supported table columns: `date, description, debit, credit`. Aliases include transaction date, narration, particulars, withdrawal, deposit, debit amount and credit amount. Also supports signed `amount` or `amount` with `type` (`DR/CR`). Positive = inflow; negative = outflow.
- Dates: ISO `YYYY-MM-DD` or Indian day-first formats. Currency: **INR only**, one account per user. Do not combine currencies or multiple accounts.
- Parser limits: 10 MB per upload, 100 PDF pages, 5,000 extracted rows, 50 MB DOCX expanded size. PDF layouts vary by bank; not every layout will parse correctly. Review counts and totals against the original. Missing rows can be added during review. Parse warnings are visible.
- Enter the actual full statement period. Partial calendar months are excluded from forecasts; zero-transaction months are included only when statement coverage verifies them. Overlapping uploads are rejected to avoid double counting. Delete a pending document and re-upload if a review is abandoned.
- `data/finpath.sqlite3` stores users, hashed sessions, parsed transactions, goals, metadata, and encrypted original-file BLOBs. SQLite BLOB storage is suitable for this bounded local project and keeps documents and metadata together. No separate database is needed merely because an upload is PDF or Word.
- File encryption uses Fernet; `data/statements.key` must be backed up securely with the database. Losing the key makes original documents unreadable. The web signing key is `data/web-session.key`. Passwords are hashed with Werkzeug scrypt; backend tokens are hashed in SQLite.
- **Parsed transactions and database metadata are not encrypted at rest.** Restrict access to the data folder or use encrypted disks. The file key is stored on the same host; this is not a managed key vault. Never commit `.env`, data files, backups or keys.
- Deleting a statement removes its active database record and transactions; it is not a secure-erasure guarantee for SQLite journals or backups.

For public deployment, use a Python-capable host (this project is not a static-site bundle), a production WSGI server for Flask, Uvicorn workers for FastAPI, HTTPS, managed secret storage, durable per-user storage, robust distributed rate limits and upload scanning. At larger scale, use PostgreSQL for structured records and encrypted private object storage for documents. This local build does not include password reset, MFA, production observability, bank connectors, OCR, or a regulatory compliance assessment.

## Project structure

```text
backend/main.py        FastAPI routes, authorization, uploads, chat adapter
backend/storage.py     SQLite schema, local keys, encrypted files
backend/parser.py      PDF, DOCX and CSV extraction
backend/ml.py          Hugging Face adapters and anomaly model
backend/planner.py     Coverage-aware history and goal calculations
frontend/app.py        Flask page server and authenticated API proxy
frontend/templates/   Website markup
frontend/static/      Responsive styling and browser interactions
samples/              Synthetic statement and regeneration script
tests/                Functional, parsing and privacy tests
run.py                Start both local servers
download_models.py    One-time model download
```

## Tests and validation

```bash
python -m pytest -q
```

The delivered base build was checked with automated tests for statement import and download, PDF and DOCX extraction, account isolation, overlapping periods, invalid rows, transfer exclusion, multiple-goal budgeting, authentication/session revocation, CSRF protection, anomaly detection, and no external chat call without consent. The optional PDF test uses reportlab; install it to run that fixture if it is not present. Optional pretrained-weight inference and live Groq responses require downloads/credentials and are not claimed as validated by these offline tests. See `VALIDATION.md` for the actual checks completed.

## Primary references (checked 8 October 2026)

- Chronos-Bolt model and license: https://huggingface.co/amazon/chronos-bolt-tiny
- Chronos official implementation: https://github.com/amazon-science/chronos-forecasting
- MiniLM model and license: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- Groq free-plan limits: https://console.groq.com/docs/rate-limits
- Groq data handling: https://console.groq.com/docs/your-data

Both selected Hugging Face model cards list Apache-2.0. Review model and dependency licenses when redistributing weights or deploying commercially. No weights are included here.
