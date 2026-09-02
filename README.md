# DataPilot AI Platform

An end-to-end full-stack AI platform combining **Data Preparation Agent** and **Natural Language SQL Agent** into a unified workspace (`AI-Powered Data Prep & Natural Language SQL Agent`).

---

## 🌟 Architecture Overview

The system keeps data cleaning and SQL querying logically separate:

```text
USER
 │
 │ Upload CSV / Excel
 ▼
DATA PREPARATION AGENT
 │
 ├── Profile dataset (Rows, Cols, Missing, Duplicates, Types, Outliers)
 ├── Detect data-quality issues
 ├── Generate AI cleaning recommendations
 │
 ▼
USER APPROVAL LAYER
 │
 ├── Show recommended operations & risk levels (Low, Med, High)
 ├── Strategy customization (Mean, Median, Mode, Unknown, Remove, Custom)
 ├── Preview expected impact before applying
 │
 ▼
CLEANING ENGINE
 │
 ├── Execute approved operations using Python/Pandas
 ├── Re-profile cleaned dataset & compare quality
 ├── Generate Markdown cleaning report & audit trail
 ├── Download Clean Dataset (.csv / .xlsx)
 │
 ▼
SQL DATABASE (SQLite)
 │
 ▼
USER ASKS QUESTION IN ENGLISH
 │
 ▼
SQL AGENT
 │
 ├── Inspect SQLite schema
 ├── Generate read-only SQL via Gemini
 ├── Validate SQL security (sql_validator)
 ├── Execute SQL on SQLite
 ├── Observe errors & self-correct (up to 3 retries)
 └── Generate natural language insight & Recharts visualization
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+

### 2. Environment Setup
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### 3. Backend Setup & Launch
```powershell
# Navigate to project root
cd agentic-data-platform

# Activate Python virtualenv (or create one)
python -m venv venv
.\venv\Scripts\pip install -r backend/requirements.txt

# Run integration test suite
.\venv\Scripts\python backend/tests/test_platform.py

# Start FastAPI server
$env:PYTHONPATH="backend"
.\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4. Frontend Setup & Launch
```powershell
# In a new terminal tab:
cd agentic-data-platform\frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your web browser.

---

## 🧪 Key Features

### Agent 1 — Data Preparation Agent
- **Statistical Profiling**: Row/col count, missing %, duplicate detection, IQR outliers, data types.
- **Human Approval Layer**: Risk levels (🟢 Low, 🟡 Med, 🔴 High). Outliers default to unchecked.
- **Deterministic Pandas Engine**: Imputation, duplicate removal, casing normalization, numeric/date parsing.
- **Audit Reports & Exports**: Downloads cleaned CSV/Excel files and detailed `.md` audit reports.

### Agent 2 — Natural Language SQL Agent
- **English to SQL**: Generates SQLite queries based on live schema inspection.
- **Security Validation**: Enforces read-only `SELECT`/`WITH` queries. Blocks `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`.
- **Autonomous Self-Correction**: Retries failed queries up to 3 times by analyzing error tracebacks.
- **Dynamic Charts**: Renders Bar, Line, Pie, and Stat Card metrics with Recharts.

---

## 🔐 Security & Integrity
- Gemini is used solely for structured JSON recommendation reasoning and SQL generation.
- Gemini is **never allowed to execute arbitrary Python code**.
- Original uploaded raw files are preserved permanently on disk without mutation.
