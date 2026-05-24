# DataProbe

Automated data quality analysis for PostgreSQL databases and spreadsheet files. Upload a CSV or Excel file (or connect a read-only Postgres DSN), and DataProbe profiles every column, runs AI-powered analysis over the statistics, validates every suggested SQL fix, and produces a prioritised report with a runnable remediation runbook.

---

## How It Works

```
Source (CSV / XLSX / PostgreSQL)
        │
        ▼
  Source Adapter          ← DuckDB (files) or asyncpg (PostgreSQL)
        │
        ▼
   Profiler               ← deterministic SQL aggregates per column
        │
        ▼
  Relationship Inferer    ← FK discovery (declared + heuristic)
        │
        ▼
   PII Scrubber           ← Presidio strips top-values before LLM sees them
        │
        ▼
  Claude Analyzer         ← 3 bounded LLM calls (quality · enrichment · synthesis)
        │
        ▼
  Dry-Run Validator       ← EXPLAIN (PostgreSQL) or BEGIN/ROLLBACK (DuckDB)
        │
        ▼
  Report Assembler        ← deterministic markdown from structured findings
        │
        ▼
     Report               ← health score · findings · SQL runbook · cleaned CSV export
```

**Key design invariants:**
- The LLM receives column statistics and metadata — **never raw rows**
- Every LLM response is Pydantic-validated before use; invalid findings are logged and dropped
- Source databases are **never modified** (read-only enforcement is 4-layer: Postgres role + `server_settings` + `SET TRANSACTION READ ONLY` + sqlglot allowlist)
- `🔴 Advisory` findings carry no runnable SQL; only an investigation query is provided
- Cleaned-file export is only available for file sources (DuckDB owns a disposable copy)

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind CSS, Clerk auth |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2 (async), Alembic |
| Task queue | Arq (Redis-backed async worker) |
| File engine | DuckDB (in-memory, disposable copy) |
| App database | PostgreSQL 16 |
| LLM | Anthropic Claude (`claude-sonnet-4-6`) |
| PII scrubbing | Microsoft Presidio + spaCy `en_core_web_lg` |
| Auth | Clerk |
| Credential encryption | Fernet (AES-128-CBC) |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Compose)
- A [Clerk](https://clerk.com) account (free tier is fine)
- An [Anthropic](https://console.anthropic.com) API key

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/zainbaq/data-probe.git
cd data-probe
```

### 2. Create `.env`

Copy the template and fill in the required values:

```bash
cp .env.example .env
```

```env
# PostgreSQL
POSTGRES_DB=dataprobe
POSTGRES_USER=dataprobe
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql+asyncpg://dataprobe:changeme@db:5432/dataprobe?ssl=disable

# Redis
REDIS_URL=redis://redis:6379/0

# Clerk — from https://dashboard.clerk.com → API Keys
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...

# Anthropic — from https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...

# Credential encryption — any 32-byte hex string
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
ENCRYPTION_KEY=your_32_byte_hex_key
```

### 3. Create `frontend/.env.local`

Clerk keys must also be available to Next.js at build time:

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

### 4. Start everything

```bash
docker compose up --build
```

On first run the worker downloads the spaCy `en_core_web_lg` model (~400 MB). Subsequent starts skip the download.

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

---

## Usage

1. Sign in at http://localhost:3000
2. Click **New Analysis** in the sidebar
3. Choose **CSV / Excel File** and upload your spreadsheet (up to 250 MB, single-sheet XLSX or CSV)
   — or choose **PostgreSQL Database** and paste a read-only DSN
4. Click **Run Analysis** and watch the live progress bar
5. When complete, the report opens automatically with:
   - **Health score** (0–100)
   - **Data Quality Findings** grouped by severity (Critical → Low)
   - **Relationship Map** (declared FKs + inferred joins)
   - **Enrichment Opportunities** (missing indexes, derivable columns, etc.)
   - **Apply Runbook** — phased SQL fixes (🟢 Safe → 🟡 Review → 🔴 Advisory)
   - **Download Cleaned File** (file sources only) — a CSV with all green fixes applied

---

## Project Structure

```
data-probe/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI routers (sources, jobs, reports)
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── adapters/    # PostgresAdapter + FileAdapter (DuckDB)
│   │   │   ├── profiler.py
│   │   │   ├── relationship_inferer.py
│   │   │   ├── pii_scrubber.py
│   │   │   ├── claude_analyzer.py
│   │   │   ├── dry_run_validator.py
│   │   │   ├── report_assembler.py
│   │   │   └── cleaned_file_exporter.py
│   │   ├── workers/         # Arq task definitions
│   │   └── utils/
│   ├── migrations/          # Alembic migrations
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/(app)/       # Protected routes (dashboard, jobs, reports)
│       ├── components/
│       ├── hooks/
│       └── lib/             # API client, types
├── test/                    # Sample files for testing
└── docker-compose.yml
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | asyncpg connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key (backend JWKS verification) |
| `CLERK_SECRET_KEY` | Yes | Clerk secret key |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key (frontend) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `ENCRYPTION_KEY` | Yes | 32-byte hex key for Fernet credential encryption |
| `ANTHROPIC_MODEL` | No | Model ID (default: `claude-sonnet-4-6`) |
| `MAX_UPLOAD_SIZE_MB` | No | Upload limit (default: `250`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `http://localhost:3000`) |

---

## Development Notes

**Backend code changes** are picked up automatically via the volume mount (`./backend:/app`) — no rebuild needed. Just restart the worker if you change worker code:

```bash
docker compose restart worker
```

**Frontend code changes** are hot-reloaded by Next.js dev mode.

**Database migrations** run automatically on backend startup (`alembic upgrade head`). To create a new migration after changing a model:

```bash
docker compose exec backend alembic revision --autogenerate -m "description"
```

**Rebuilding** (only needed when `requirements.txt` or `package.json` changes):

```bash
docker compose up --build
```

---

## License

MIT
