# Mira — Production Deployment & Readiness Checklist

This document serves as the operational guide and checklist for deploying Mira to staging and production environments safely, securely, and reliably.

---

## 1. Environment & Configuration Checklist

| Variable | Recommended Production Value | Notes |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Disables debug mode, auto-seeding of dev users, and sanitizes errors. |
| `DEBUG` | `False` | Enforced automatically when `ENVIRONMENT=production`. |
| `ENABLE_DOCS` | `False` | Disables `/docs`, `/redoc`, and `/openapi.json` from public internet exposure. Set to `True` only in staging/internal networks if required. |
| `LOG_LEVEL` | `INFO` | Emits structured timestamped logs without verbose debug noise. |
| `CORS_ORIGINS` | `["https://mira.yourdomain.com"]` | **Never** use `*` or wildcard domains in production. Set explicitly to authorized client domains. |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@db-host:5432/mira_prod?sslmode=require` | Use managed PostgreSQL (RDS, Supabase, Neon) with SSL enabled. Do not use SQLite in production. |
| `DATABASE_POOL_SIZE` | `10`–`20` | Sized according to server concurrency and database max connections. |
| `DATABASE_MAX_OVERFLOW` | `20`–`40` | Maximum surge connections allowed above `pool_size`. |
| `DATABASE_POOL_RECYCLE` | `1800`–`3600` | Recycles idle connections to avoid stale connections dropped by firewalls. |
| `AI_PROVIDER` | `mock` / `openai` / `gemini` | Chosen AI roadmap generation provider. |
| `AI_API_KEY` | *(Secret Vault)* | Injected via environment secret manager (e.g., AWS Secrets Manager, Doppler, Doppler, Render/Fly secrets). |

---

## 2. Security Hardening Checklist

- [x] **HTTP Security Headers**: Injected automatically by Mira middleware on all responses:
  - `X-Content-Type-Options: nosniff` (Prevents MIME sniffing attacks)
  - `X-Frame-Options: DENY` (Mitigates clickjacking)
  - `Referrer-Policy: strict-origin-when-cross-origin` (Protects referrer leakage)
  - `Permissions-Policy: geolocation=(), camera=(), microphone=()` (Restricts browser device APIs)
- [x] **Exception Sanitization**:
  - Global unhandled exception handler intercepts unexpected errors in production.
  - Returns safe, sanitized error payload: `{"detail": "An internal server error occurred. Please try again later."}`.
  - Detailed stack traces and paths are logged internally to server logs and never exposed to clients.
- [x] **No Hardcoded Secrets**:
  - All credentials, API keys, and database passwords must be provided through environment variables.
  - `.env` is strictly gitignored.
- [x] **Seed Data Disabled in Production**:
  - Automatic `dev_user` creation on startup only executes when `ENVIRONMENT=development`.
  - In production, user records must be provisioned through formal onboarding or migration pipelines.
- [x] **CORS Guardrails**:
  - Browsers reject responses where `Access-Control-Allow-Origin: *` and credentials are true. Mira automatically handles and validates CORS origins and enforces proper credential flags.
- [x] **XSS & Injection Protection**:
  - Zero instances of `dangerouslySetInnerHTML` in frontend code.
  - All database interactions use SQLAlchemy ORM parameterized queries (zero string-interpolated SQL).

---

## 3. Database & Migration Checklist

1. **Pre-Deployment Migrations**:
   Run database schema migrations before redirecting user traffic:
   ```bash
   python -m alembic upgrade head
   ```
2. **Schema Drift Verification**:
   Verify that models and migrations match:
   ```bash
   python -m alembic check
   ```
3. **Connection Pooling**:
   - `pool_pre_ping=True` is enabled to automatically detect and discard stale or closed connections before handing them to a request.
   - Adjust `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW` based on worker processes (`workers * pool_size < postgres_max_connections`).
4. **Backups**:
   - Configure automated daily snapshots with point-in-time recovery (PITR) for PostgreSQL.

---

## 4. Observability & Health Probes

Mira provides separated endpoints for container orchestration (Kubernetes, AWS ECS, Fly.io, Render):

### Liveness Probe
- **Endpoints**: `GET /health` or `GET /api/v1/health`
- **Response**: `200 OK` `{"status": "ok", "app": "Mira"}`
- **Purpose**: Fast check verifying the Python process and event loop are responsive. Does **not** perform database I/O to avoid false restarts during database spikes.

### Readiness Probe
- **Endpoints**: `GET /ready` or `GET /api/v1/ready`
- **Response**: `200 OK` `{"status": "ready", "database": "connected"}` or `503 Service Unavailable` `{"status": "unhealthy", "database": "disconnected"}`
- **Purpose**: Verifies database connectivity using an active `SELECT 1` query. Load balancers should only route user traffic when this returns 200.

---

## 5. Frontend Production Build & Asset Delivery

1. **Production Build**:
   ```bash
   cd frontend
   npm run build
   ```
   Generates optimized, minified bundle in `frontend/dist/`.

2. **Environment Variable Configuration**:
   - Set `VITE_API_BASE_URL` in build environment if the API is served from a separate domain (e.g. `https://api.mira.yourdomain.com/api/v1`).
   - If using a reverse proxy (e.g. Nginx proxying `/api` to the backend), leave `VITE_API_BASE_URL=/api/v1`.

3. **Serving Recommendations**:
   - Serve static assets via CDN (Cloudflare, AWS CloudFront, Fastly) or an optimized web server (Nginx, Caddy).
   - Configure cache headers:
     - `index.html`: `Cache-Control: no-cache, no-store, must-revalidate`
     - Assets in `/assets/*` (hashed filenames): `Cache-Control: public, max-age=31536000, immutable`

---

## 6. Pre-Flight Verification Script

Run the following test commands prior to merging or deploying:

```bash
# 1. Run all backend unit & integration tests
python -m pytest backend/tests -v

# 2. Check database migrations
python -m alembic check

# 3. Test frontend TypeScript and production bundle compilation
cd frontend
npm run build
```
