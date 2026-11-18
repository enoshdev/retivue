# RETIVUE — Backend & Database Infrastructure (Phase 1)

This directory contains the production-oriented FastAPI backend and PostgreSQL database infrastructure powering the **RETIVUE** AI-assisted diabetic retinopathy screening and clinical decision-support platform.

---

## 1. Required Software & Prerequisites

- **Python**: Version `3.12` (verified on Python 3.12.10 x64)
- **PostgreSQL**: Version `18` (or 15+) installed locally
- **Node.js**: Version `18+` / `20+` (for the Next.js frontend)
- **Shell**: Windows PowerShell

---

## 2. Directory Structure

```text
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── health.py        # /api/health and /api/health/database endpoints
│   ├── core/
│   │   ├── config.py            # Pydantic v2 settings & environment parsing
│   │   └── logging.py           # Structured logging with credential sanitization
│   ├── database/
│   │   ├── base.py              # SQLAlchemy 2.x DeclarativeBase
│   │   └── session.py           # AsyncSession generator, connection pooling, check_db_health
│   ├── models/                  # Registered SQLAlchemy ORM models
│   ├── schemas/
│   │   └── health.py            # Pydantic v2 response contracts
│   ├── services/                # Business logic services (Phase 2+)
│   ├── repositories/            # Data access layer (Phase 2+)
│   └── main.py                  # Single clear FastAPI entry point
├── migrations/
│   ├── versions/                # Alembic revision scripts
│   │   └── d318994b5a41_initial_schema.py
│   └── env.py                   # Migration environment connected to Base.metadata
├── tests/
│   ├── conftest.py              # Pytest async fixtures (AsyncClient, engine override)
│   └── test_infrastructure.py   # Test suite for health, database, CORS, migrations
├── .env.example                 # Documented configuration template (no secrets)
├── .env                         # Local development secrets (git-ignored)
├── alembic.ini                  # Alembic CLI configuration
├── pytest.ini                   # Pytest async configuration
├── requirements.txt             # Pinned backend dependencies
└── README.md                    # Technical documentation
```

---

## 3. Python Environment & Dependency Setup

Run the following commands in Windows PowerShell:

```powershell
# Navigate to the backend directory
cd backend

# Create virtual environment with Python 3.12
py -3.12 -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install all backend dependencies (FastAPI, SQLAlchemy 2.x, Psycopg 3, Asyncpg, Alembic)
pip install -r requirements.txt
```

---

## 4. PostgreSQL Local Database Setup

RETIVUE utilizes a dedicated PostgreSQL database cluster with SCRAM-SHA-256 authentication:

- **Cluster Path**: `$env:LOCALAPPDATA\retivue\pgdata`
- **Port**: `5433` (configured to prevent conflicts with default service ports)
- **Database**: `retivue`
- **User**: `retivue_user`
- **Password**: Configured in `backend/.env` (e.g. `RetiVue_Dev_2026_Secure!`)

### Initializing and Starting the PostgreSQL Cluster (Windows PowerShell)

```powershell
# 1. Initialize cluster with SCRAM-SHA-256 authentication
$pgData = "$env:LOCALAPPDATA\retivue\pgdata"
$pwFile = "$env:TEMP\retivue_pw.txt"
"RetiVue_Dev_2026_Secure!" | Out-File -FilePath $pwFile -Encoding ascii -NoNewline

& "C:\Program Files\PostgreSQL\18\bin\initdb.exe" -D $pgData -U retivue_user --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwfile=$pwFile
Remove-Item $pwFile -Force

# 2. Configure port 5433 in postgresql.conf
Add-Content -Path "$pgData\postgresql.conf" -Value "`nport = 5433`nlisten_addresses = '127.0.0.1'`n"

# 3. Start PostgreSQL server daemon
& "C:\Program Files\PostgreSQL\18\bin\postgres.exe" -D $pgData -p 5433

# 4. Create the dedicated database
$env:PGPASSWORD = "RetiVue_Dev_2026_Secure!"
& "C:\Program Files\PostgreSQL\18\bin\createdb.exe" -h 127.0.0.1 -p 5433 -U retivue_user retivue
```

---

## 5. Environment Variables Configuration

Copy `.env.example` to `.env` in the `backend/` directory:

```powershell
Copy-Item .env.example .env
```

Ensure `.env` contains:

```env
PROJECT_NAME="RETIVUE Clinical Backend"
APP_ENV="development"
ENVIRONMENT="development"
SECRET_KEY="retivue-development-secret-key-change-in-production-only"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# PostgreSQL Connection Configuration
POSTGRES_SERVER="127.0.0.1"
POSTGRES_PORT=5433
POSTGRES_USER="retivue_user"
POSTGRES_PASSWORD="RetiVue_Dev_2026_Secure!"
POSTGRES_DB="retivue"

# Database Connection URLs
# Async engine for FastAPI endpoints
DATABASE_URL="postgresql+asyncpg://retivue_user:RetiVue_Dev_2026_Secure!@127.0.0.1:5433/retivue"

# Sync engine (Psycopg 3) for Alembic migrations
SYNC_DATABASE_URL="postgresql+psycopg://retivue_user:RetiVue_Dev_2026_Secure!@127.0.0.1:5433/retivue"

# Connection Pooling
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_CONNECT_TIMEOUT=5

# Frontend Integration & CORS
FRONTEND_ORIGIN="http://localhost:3000"
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

---

## 6. Alembic Database Migrations

Alembic inspects model definitions in `app/models/` registered on `Base.metadata` and syncs schema changes with PostgreSQL.

```powershell
# Check current migration revision
.\.venv\Scripts\alembic.exe current

# Show migration history
.\.venv\Scripts\alembic.exe history --verbose

# Apply migrations to database (upgrade to head)
.\.venv\Scripts\alembic.exe upgrade head

# Roll back migration (downgrade to base)
.\.venv\Scripts\alembic.exe downgrade base

# Verify schema synchronization (autogeneration diff check)
.\.venv\Scripts\alembic.exe check
```

---

## 7. Starting the Backend Server

Start the FastAPI development server with Uvicorn:

```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 8. Starting the Frontend Server

From the repository root:

```powershell
# Start Next.js development server
npm run dev
```

The frontend will run at [http://localhost:3000](http://localhost:3000).

---

## 9. Health Endpoints & Diagnostics

### 1. Backend Health Check
- **URL**: `GET http://127.0.0.1:8000/api/health`
- **Status Code**: `200 OK`
- **Response**:
  ```json
  {
    "status": "healthy",
    "project": "RETIVUE Clinical Backend",
    "environment": "development",
    "version": "1.0.0"
  }
  ```

### 2. Database Connectivity Health Check
- **URL**: `GET http://127.0.0.1:8000/api/health/database`
- **Status Code (Healthy)**: `200 OK`
- **Response**:
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "latency_ms": 1.25,
    "message": "Database connected and responsive."
  }
  ```
- **Status Code (Unhealthy)**: `503 Service Unavailable`
- **Response**:
  ```json
  {
    "status": "unhealthy",
    "database": "disconnected",
    "latency_ms": 5000.0,
    "message": "Database connectivity check failed."
  }
  ```

---

## 10. Executing Automated Tests

Run the backend test suite via `pytest`:

```powershell
cd backend
.\.venv\Scripts\pytest.exe -v tests
```

### Verified Test Cases:
1. `test_root_endpoint` — Validates root JSON response and status links.
2. `test_backend_health_endpoint` — Validates operational status of FastAPI app.
3. `test_database_health_endpoint_success` — Tests live `SELECT 1` query execution against PostgreSQL.
4. `test_database_health_endpoint_failure_handling` — Simulates DB outage, verifies HTTP 503 response and checks that no credentials are leaked.
5. `test_cors_allowed_frontend_origin` — Verifies CORS headers for `http://localhost:3000`.
6. `test_cors_preflight_options` — Verifies preflight OPTIONS response.
7. `test_cors_disallowed_origin` — Rejects untrusted origins.
8. `test_alembic_migration_recorded_in_postgres` — Validates that PostgreSQL records the applied Alembic migration version.
9. `test_unhandled_route_returns_404` — Verifies 404 handling.

---

## 11. Common Setup Issues & Solutions

1. **`psycopg2.OperationalError: connection to server at '127.0.0.1', port 5433 failed: Connection refused`**
   - **Cause**: PostgreSQL daemon is not running on port 5433.
   - **Fix**: Launch PostgreSQL using `& "C:\Program Files\PostgreSQL\18\bin\postgres.exe" -D "$env:LOCALAPPDATA\retivue\pgdata" -p 5433`.

2. **`fe_sendauth: password authentication failed for user 'retivue_user'`**
   - **Cause**: Password in `.env` does not match the password supplied during `initdb`.
   - **Fix**: Verify `POSTGRES_PASSWORD` in `backend/.env` matches `RetiVue_Dev_2026_Secure!`.

3. **`CORS Request Blocked` from Frontend**
   - **Cause**: Frontend is running on an origin not in `BACKEND_CORS_ORIGINS`.
   - **Fix**: Add the origin to `BACKEND_CORS_ORIGINS` in `backend/.env` (e.g. `["http://localhost:3000"]`).

