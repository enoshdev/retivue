# RETIVUE — Deployment & Operations Guide

## 1. System Overview

RETIVUE is a clinical screening platform for diabetic retinopathy with integrated quality-gated research AI decision support. It consists of:
- **Frontend**: Next.js 16 (App Router, Tailwind CSS, TypeScript).
- **Backend**: FastAPI (Python 3.12, AsyncPG, SQLAlchemy 2.0, Alembic, PyTorch).
- **Database**: PostgreSQL 18.
- **Storage**: Private encrypted object storage (local filesystem or S3-compatible).
- **AI Models**: Preserved EfficientNet-B0 research checkpoints (E0, E1, E2) with mandatory SHA-256 integrity verification.

---

## 2. Environment Configuration

### Backend (`backend/.env`)

```ini
APP_ENV=production
PROJECT_NAME="RETIVUE Clinical Platform"
# Minimum 32-character random secret key
SECRET_KEY=generate_strong_64_character_hex_string_here

# PostgreSQL 18
POSTGRES_SERVER=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_USER=retivue_user
POSTGRES_PASSWORD=use_strong_database_password
POSTGRES_DB=retivue
DATABASE_URL=postgresql+asyncpg://retivue_user:password@127.0.0.1:5433/retivue
SYNC_DATABASE_URL=postgresql+psycopg://retivue_user:password@127.0.0.1:5433/retivue

# Session and Cookie Security
COOKIE_SECURE=True
COOKIE_SAMESITE=lax
COOKIE_PATH=/
SESSION_MAX_AGE_SECONDS=2592000

# CORS Permitted Frontend Origins (No wildcard or localhost in production)
BACKEND_CORS_ORIGINS=["https://app.retivue.org"]

# Secure Storage Root
LOCAL_STORAGE_ROOT=C:\ProgramData\retivue\private_storage
MODEL_ROOT=C:\ProgramData\retivue\models
```

### Frontend (`.env.production`)

```ini
NEXT_PUBLIC_API_URL=https://api.retivue.org
```

---

## 3. Database Migration Procedures

Run database migrations using Alembic:

```powershell
cd backend
.\.venv\Scripts\alembic.exe upgrade head
```

Verify current revision:

```powershell
.\.venv\Scripts\alembic.exe current
# Expected head: a7c4d9e8f102
```

---

## 4. Backup & Disaster Recovery

### Automated Backup Script (`scripts/backup_retivue.ps1`)

Exports PostgreSQL dump and syncs private retinal storage:

```powershell
param(
    [string]$BackupDir = "C:\backups\retivue"
)
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$DumpFile = "$BackupDir\retivue_db_$Timestamp.sql"
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -h 127.0.0.1 -p 5433 -U retivue_user -d retivue -F c -f $DumpFile
```

### Recovery Script (`scripts/restore_retivue.ps1`)

Restores PostgreSQL database from backup archive:

```powershell
param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)
& "C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" -h 127.0.0.1 -p 5433 -U retivue_user -d retivue -c --if-exists $BackupFile
```

---

## 5. Security & Operational Rules

1. **Autonomous Diagnosis Forbidden**: AI outputs must never be presented as final diagnosis.
2. **Practitioner Sign-Off Required**: Medical registration numbers are validated before signing clinical assessments.
3. **Strict Data Isolation**: Account ownership is enforced across all tables and private storage paths.
4. **Controlled Pilot Deployment**: Deployment to real clinical patient-care environments requires institutional ethics approval, clinical pilot sign-off, and medical device regulatory clearance.
