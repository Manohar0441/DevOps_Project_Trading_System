# 📈 SwingEdge — Automated Swing Trading Strategy Platform

> **A rules-based, fully automated swing trading platform** for Indian (NSE/BSE) and US (NYSE/NASDAQ) equities.
> Built as a microservice system deployed on AWS EKS with a Jenkins CI/CD pipeline.

**Stack:** Python · FastAPI · React · PostgreSQL · Redis · AWS SQS · Docker · Kubernetes · Jenkins · Terraform

---

## 📌 Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Architecture Overview](#2-architecture-overview)
3. [Microservices Breakdown](#3-microservices-breakdown)
4. [Folder Structure](#4-folder-structure)
5. [Tech Stack (Interview Cheatsheet)](#5-tech-stack-interview-cheatsheet)
6. [Event-Driven Design (SQS)](#6-event-driven-design-sqs)
7. [Database Architecture](#7-database-architecture)
8. [Circuit Breakers & Resilience](#8-circuit-breakers--resilience)
9. [CI/CD Pipeline — Jenkins](#9-cicd-pipeline--jenkins)
10. [Docker Strategy](#10-docker-strategy)
11. [Kubernetes on AWS EKS](#11-kubernetes-on-aws-eks)
12. [AWS Infrastructure](#12-aws-infrastructure)
13. [Observability — Metrics, Traces, Logs](#13-observability--metrics-traces-logs)
14. [Secrets & Config Management](#14-secrets--config-management)
15. [Real-Time Updates — SSE](#15-real-time-updates--sse)
16. [Distributed Tracing — OpenTelemetry + Jaeger](#16-distributed-tracing--opentelemetry--jaeger)
17. [Immutable Audit Log](#17-immutable-audit-log)
18. [Feature Flags](#18-feature-flags)
19. [Contract Testing — Pact](#19-contract-testing--pact)
20. [Local Development Setup](#20-local-development-setup)
21. [Interview Q&A — Key Design Decisions](#21-interview-qa--key-design-decisions)

---

## 1. What This Project Does

SwingEdge enforces a **disciplined, emotion-free 3-month swing trading cycle** through automated pipelines. No manual intervention during live cycles.

| Pillar | What It Does |
|---|---|
| **Screening** | Filters universe by quarterly EPS momentum (Q_N > Q_N-1, ≥5% sequential growth) |
| **Scoring** | Ranks each candidate across 14 metrics (growth, profitability, financial health, valuation) |
| **Portfolio Construction** | Allocates capital across top stocks; enforces sector limits and position sizing |
| **Risk Management** | Applies week-specific stop-loss and profit-lock rules in real-time |
| **Event Bus** | Async SQS events for SL hits, profit locks, exit deadlines — no polling |
| **Batch Jobs** | HA-scheduled quarterly/monthly jobs via Celery + RedBeat |
| **Dashboard** | Real-time React UI with SSE event streaming |
| **Notifications** | Push alerts via AWS SNS (SMS) + SES (email) on every rule trigger |
| **Audit Log** | Append-only, immutable record of every trade action for compliance |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                        │
│            React SPA (Dashboard, Tracker, SSE)          │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTPS / SSE
┌─────────────────────▼───────────────────────────────────┐
│     CloudFront → Route 53 → ALB → NGINX Ingress         │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              AWS EKS (Kubernetes Cluster)                │
│                                                         │
│  frontend   screening   scoring   portfolio   risk       │
│  (Nginx)    (FastAPI)  (FastAPI)  (FastAPI)  (FastAPI)  │
│                                                         │
│  batch        notification    data-validator             │
│  (Celery+     (FastAPI +      (FastAPI +                │
│   RedBeat)     SQS consumer)   Great Expectations)      │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │         AWS SQS Event Bus (6 Queues + DLQs)      │   │
│  │  stop-loss · profit-lock · exit-deadline         │   │
│  │  macro-override · screening-complete · audit     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    DATA LAYER                           │
│  PostgreSQL RDS (Multi-AZ) — one schema per service     │
│  Redis (ElastiCache) — Celery broker + feature flags    │
│  AWS S3 — reports, market-data cache, Terraform state   │
└─────────────────────────────────────────────────────────┘

EXTERNAL DATA: NSE API → Alpha Vantage → S3 cache (fallback chain)

OBSERVABILITY:
  Prometheus → Grafana     (metrics)
  OpenTelemetry → Jaeger   (traces)
  Fluent Bit → CloudWatch  (logs)
  Alertmanager → PagerDuty (ops alerts)

CI/CD:
  GitHub → Jenkins → Lint/Test/Pact → Docker Build
  → Trivy Scan → ECR → Canary Deploy (10%) → Metric Gate
  → Promote 100%  OR  Auto Rollback
```

---

## 3. Microservices Breakdown

### `scoring-service` · Port 8000
- Entry point: `main.py` → `ManualScoringPipeline`
- Reads from `inputs/`, writes to `outputs/`
- Scores each stock 0–100 across 4 categories:
  - **Growth Quality** (30%) — EPS >10%, Revenue >8%, OCF/NI >1.0
  - **Profitability** (25%) — Operating Margin >15%, ROIC >12%, ROE >12%
  - **Financial Health** (20%) — D/E <2.0, Current Ratio >1.5, Interest Coverage >3×
  - **Valuation Sanity** (15%) — P/E <Industry+30%, PEG <1.5, EV/EBITDA <15×

### `batch-service` · Port 8001
- Runs scheduled jobs via **Celery + RedBeat** (Redis-backed scheduler)
- Every job is idempotent — Redis lock prevents double execution
- Key jobs: `quarterly_screen`, `daily_price_update`, `risk_evaluation`, `exit_deadline_check`

### `frontend-service` · Port 8080
- React 18 SPA served via Nginx
- Connects to `risk-service` via **SSE** for real-time event streaming
- Pages: Dashboard, Trade Tracker, Checklist, Cycle Review, Calendar, Audit Trail

### `portfolio-service` · Port 8003
- Implements final capital allocation (Query 5 of Research Protocol)
- Enforces: min ₹5,000/position, no single sector >60%, India sector ≠ USA sector

### `risk-service` · Port 8004
- **Most critical service** — evaluates risk rules every 30 min during market hours
- Week-specific SL rules enforced (Week 1–13 cycle):
  - +5% → move SL to breakeven
  - +10% → book 40%, SL to +6%
  - +15% → exit or trail weekly
  - Week 13 → mandatory full exit
- Publishes SQS events on every trigger
- Exposes `/api/v1/risk/stream` SSE endpoint to frontend

### `screening-service` · Port 8005
- Implements quarterly momentum filter: Q_N > Q_N-1, min +5% EPS sequential growth
- Produces top 25 India + top 25 USA candidates
- Publishes `SCREENING_COMPLETE` event to SQS on completion

### `notification-service` · Port 8006
- Pure SQS consumer — never called directly by other services
- Routes alerts to AWS SES (email) or SNS (SMS) based on event type and severity
- Critical alerts (SL hit, mandatory exit) trigger both SMS + email

### `data-validator-service`
- Sits between all external data sources and internal services
- Validates schema, ranges, staleness, split-adjustments, outliers (>3σ flags)
- Implements 3-tier fallback: NSE/yfinance → Alpha Vantage → S3 cache

### `common` (shared library)
- Installed as a local Python package into all services
- Contains: ORM models, Pydantic schemas, SQS publisher/consumer base classes, circuit breaker, OpenTelemetry init, AuditLogWriter, structured logger, feature flag client

---

## 4. Folder Structure

```
DevOps_Project_Trading_System/
│
├── services/
│   ├── common/              # Shared library — installed into all services
│   ├── scoring_service/     # Stock scorer (main entry point)
│   ├── batch_service/       # Celery + RedBeat scheduled jobs
│   ├── frontend_service/    # React SPA + Nginx
│   ├── portfolio_service/   # Capital allocation
│   ├── risk_service/        # Risk rule engine + SSE stream
│   ├── screening_service/   # Quarterly stock screener
│   ├── notification_service/# SQS consumer → SNS/SES alerts
│   └── data_validator_service/ # Market data validation + fallback chain
│
├── infra/
│   ├── terraform/           # All AWS infra as code (EKS, RDS, SQS, S3, IAM)
│   ├── helm/swingEdge/      # Helm chart for K8s (deployments, HPA, PDB, NetworkPolicy)
│   ├── jenkins/             # Jenkinsfile (canary pipeline) + shared library
│   └── monitoring/          # Prometheus, Grafana dashboards, Jaeger, Alertmanager
│
├── config/                  # Environment configs (dev/staging/prod)
├── inputs/                  # Stock JSON input files
├── outputs/MSFT/            # Scored output files
├── tests/
│   ├── integration/         # Cross-service integration tests
│   ├── e2e/                 # Full cycle end-to-end tests
│   └── contract/            # Pact consumer contract tests
│
├── main.py                  # CLI entry point for manual scoring
├── batchrunner.py           # Local batch job runner
├── auto_peers_web.py        # Auto peer stock fetcher
├── stocks.txt               # Watchlist of stock tickers
├── docker-compose.yml       # Full local stack
└── docker-compose.dev.yml   # Dev-mode overrides
```

---

## 5. Tech Stack (Interview Cheatsheet)

| Category | Technology | Why Used |
|---|---|---|
| **Backend** | Python 3.11, FastAPI, Pydantic v2 | Async, type-safe APIs; auto-generated OpenAPI docs |
| **Task Queue** | Celery + RedBeat | Async jobs; RedBeat uses Redis as scheduler (eliminates single-point-of-failure vs default Beat) |
| **Message Broker/Cache** | Redis 7 (AWS ElastiCache) | Celery broker, RedBeat schedule store, feature flags, rate-limit counters |
| **Event Bus** | AWS SQS (FIFO, 6 queues) | Decouples producers/consumers; FIFO ensures ordered event processing; DLQ catches failures |
| **Database** | PostgreSQL 15 (AWS RDS Multi-AZ) | One schema per service — service isolation without separate DB instances |
| **ORM/Migrations** | SQLAlchemy + Alembic | Schema-per-service session factories; per-schema Alembic version dirs |
| **Frontend** | React 18, TypeScript, TailwindCSS, Vite | Fast SPA with SSE-powered real-time events |
| **Resilience** | resilience4py (circuit breakers) | Prevents cascading failures when downstream services are slow |
| **Tracing** | OpenTelemetry → Jaeger | One trace ID flows across all services; spans auto-captured for HTTP, DB, SQS |
| **Data Validation** | Great Expectations | Declarative market data quality rules with range checks and schema validation |
| **Contract Testing** | Pact | Consumer-driven contract tests prevent API breaking changes between services |
| **Feature Flags** | Redis-backed (custom) | Roll out logic changes progressively without redeploy |
| **Containers** | Docker (multi-stage, non-root) | Lean production images; builder stage isolates build tools from runtime |
| **Orchestration** | Kubernetes (AWS EKS) | HPA, PDB, NetworkPolicy, IRSA, rolling deploys, canary |
| **Helm** | Helm 3 | Parameterised K8s manifests; per-environment `values-*.yaml` |
| **CI/CD** | Jenkins (EC2) | Canary pipeline: lint → test → contract → build → scan → deploy → metric gate |
| **IaC** | Terraform | VPC, EKS, RDS, ElastiCache, SQS, S3, IAM, WAF, Route53, CloudFront |
| **Container Registry** | AWS ECR | Image vulnerability scanning on push; lifecycle policy keeps last 10 tagged images |
| **Secrets** | AWS Secrets Manager + External Secrets Operator | Secrets live in AWS; ESO syncs them into K8s Secrets on a 1-hour refresh cycle |
| **Monitoring** | Prometheus + Grafana | Custom business metrics (SL triggers, profit locks) + system metrics per service |
| **Logging** | Fluent Bit → CloudWatch | Structured JSON logs with trace_id correlation; shipped as DaemonSet |
| **Notifications** | AWS SNS (SMS) + SES (email) | CRITICAL alerts (SL hit, mandatory exit) via SMS; summaries via email |
| **CDN/DNS** | CloudFront + Route 53 | Edge caching for static assets; long TTL on hashed filenames |
| **Security** | AWS WAF + NetworkPolicy + IRSA | WAF rate-limits at ALB; NetworkPolicy enforces zero-trust between pods; IRSA removes long-lived keys |

---

## 6. Event-Driven Design (SQS)

**Why SQS?** A slow `notification-service` must never block `risk-service` from evaluating positions. SQS decouples the two.

### Queue Map

| Queue | Producer | Consumer | Priority |
|---|---|---|---|
| `swingedge-stop-loss-events` | risk-service | notification-service | CRITICAL |
| `swingedge-profit-lock-events` | risk-service | notification-service, frontend relay | HIGH |
| `swingedge-exit-deadline-events` | risk-service, batch-service | notification-service | HIGH |
| `swingedge-macro-override-events` | batch-service | risk-service, notification-service | MEDIUM |
| `swingedge-screening-complete-events` | screening-service | scoring-service | LOW |
| `swingedge-audit-events` | all services | audit-writer | LOW |

### Key Design Choices
- **FIFO queues** — message deduplication ID prevents duplicate alerts (e.g. same SL triggered twice)
- **Long polling** (`WaitTimeSeconds=20`) — reduces empty receive calls by up to 95%
- **DLQ policy** — after 3 failed attempts, message goes to DLQ; CloudWatch alarm fires on DLQ depth > 0
- **VPC Endpoint for SQS** — traffic never leaves the AWS network

### Event Envelope
Every event carries: `event_id`, `event_type`, `source`, `trace_id`, `occurred_at`, `payload`

---

## 7. Database Architecture

**Design decision:** One PostgreSQL schema per service. All services share the same RDS instance (cost-effective) but each service has its own DB user with permissions only to its schema. Cross-service data is always fetched via API — never via direct DB query.

### Schema Map

| Service | Schema | DB User | Key Tables |
|---|---|---|---|
| screening | `screening` | `swe_screening` | screen_runs, candidates, sector_rankings |
| scoring | `scoring` | `swe_scoring` | score_results, checklist_results |
| portfolio | `portfolio` | `swe_portfolio` | cycles, positions, allocation_plans |
| risk | `risk` | `swe_risk` | risk_evaluations, sl_history, heat_log |
| batch | `batch` | `swe_batch` | job_runs, job_locks |
| notification | `notify` | `swe_notify` | notification_log |
| audit | `audit` | `swe_audit_ro` (read-only app user) | audit_log (append-only) |

### Alembic Per-Schema Migrations
```bash
alembic --name screening upgrade head
alembic --name scoring   upgrade head
# Run in Jenkins deploy stage — never by hand in production
```

### RDS Config (Production)
- Multi-AZ: Yes (automatic failover)
- Read Replica: 1 (for reporting queries)
- Point-in-Time Recovery: Enabled
- Encryption at rest: AWS KMS
- Automated backups: 7-day retention

---

## 8. Circuit Breakers & Resilience

Every external call is wrapped in a circuit breaker using `resilience4py`. If a downstream service fails repeatedly, the circuit opens and the caller gets a fast failure (not a slow timeout) with a defined fallback.

### Circuit Breaker Map

| Caller | Called Service | Threshold | Recovery | Fallback |
|---|---|---|---|---|
| screening | data-validator | 5 failures | 30s | Last S3 cache (stale=True) |
| scoring | screening | 5 failures | 30s | Return cached score |
| portfolio | scoring | 3 failures | 20s | Halt + alert |
| risk | notification | 5 failures | 30s | Publish to SQS (notification catches it) |
| batch | risk | 3 failures | 60s | Skip eval + alert |
| data-validator | yfinance (external) | 3 failures | 60s | Alpha Vantage |
| data-validator | Alpha Vantage | 3 failures | 120s | S3 cache |

### Retry Strategy
Exponential backoff with jitter: `delay = base * 2^attempt + random(0, 0.5s)`

---

## 9. CI/CD Pipeline — Jenkins

### Pipeline Stages
```
GitHub push/tag
    │
    ▼
1. Checkout + Detect Changed Services (git diff)
2. Lint (flake8, black, mypy) + Frontend ESLint — in parallel
3. Unit Tests (pytest, ≥70% coverage) → JUnit XML report
4. Contract Tests (Pact broker verification)
5. Docker Build (only changed services)
6. Security Scan (Trivy — blocks on CRITICAL CVEs)
7. Push to AWS ECR
8. Deploy to Dev namespace → Smoke tests
9. Integration Tests (cross-service)
10. [main branch] Deploy Canary to Staging → Smoke tests
11. [v* tag] Deploy Canary to Production (10% traffic)
    └── Wait 5 minutes → Metric Gate:
        ├── Error rate < 1%?
        ├── P99 latency < 500ms?
        └── No circuit breakers opened?
            ├── PASS → Promote to 100%
            └── FAIL → helm rollback + alert team
```

### Branch Strategy
| Branch | Deploys To | Notes |
|---|---|---|
| `feature/*` | Dev (on PR merge) | Short-lived, rebased onto main |
| `main` | Staging canary | Always deployable |
| `v*` tags (e.g. `v1.2.0`) | Production canary | Semantic versioning |
| `hotfix/*` | Staging → Prod fast-track | Bypasses full staging cycle |

### Key Jenkins Details
- **Optimisation:** Only builds/deploys services with changed files (git diff)
- **OIDC auth:** Jenkins uses OIDC IAM role — no AWS access keys stored on disk
- **Pact Broker:** Contract tests run before build; a broken contract blocks deployment
- **Trivy:** `--exit-code 1 --severity CRITICAL` — CRITICAL CVEs break the build

---

## 10. Docker Strategy

### Multi-Stage Python Dockerfile
```dockerfile
# Stage 1: Builder — installs deps (pip, build tools)
FROM python:3.11-slim AS builder
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Production — no pip, no build tools, non-root user
FROM python:3.11-slim AS production
COPY --from=builder /install /usr/local   # Only the installed packages
COPY services/common /app/common          # Shared lib (changes less = better caching)
COPY services/{svc}/app /app
RUN useradd -u 1001 appuser && chown -R appuser /app
USER appuser                              # Never run as root
CMD ["uvicorn", "main:app", "--timeout-graceful-shutdown", "30"]
```

### Key Decisions
- **Multi-stage builds** — production image has no pip, no build tools (~60% smaller)
- **Non-root user** — required by most K8s security policies
- **Layer caching** — `common/` and `requirements.txt` copied before app code (they change less often)
- **Graceful shutdown** — `--timeout-graceful-shutdown 30` lets in-flight requests complete before SIGTERM
- **HEALTHCHECK** — `curl /health` every 30s; K8s also has liveness/readiness probes

### Docker Compose (Local Dev)
- `docker-compose.yml` — full production-like stack (7 services)
- `docker-compose.dev.yml` — dev overrides (hot reload, debug ports)
- **LocalStack** replaces AWS services locally: SQS, S3, SES, SNS (`http://localstack:4566`)

---

## 11. Kubernetes on AWS EKS

### Per-Service K8s Resources (all managed via Helm)

**Deployment** — rolling update with `maxUnavailable: 0` (zero-downtime)

**HPA** — scales on CPU (60%) and memory (70%), min 2 / max 8 replicas

**PodDisruptionBudget** — `minAvailable: 1` ensures at least one pod survives node drains and upgrades

**NetworkPolicy (Zero-Trust)** — each pod explicitly declares which pods it can receive from and send to. Default: deny all. Example: `risk-service` can only be called by `ingress-nginx` and `portfolio-service`.

**ExternalSecrets** — AWS Secrets Manager values synced into K8s Secrets every hour via External Secrets Operator

**ResourceQuota** — per namespace limit on CPU/memory/pods prevents runaway resource consumption

### Probe Strategy
```yaml
livenessProbe:
  httpGet: { path: /health, port: 8004 }
  initialDelaySeconds: 20      # Wait for startup
  failureThreshold: 3          # 3 consecutive failures → restart pod

readinessProbe:
  httpGet: { path: /ready, port: 8004 }
  initialDelaySeconds: 10
  failureThreshold: 2          # 2 failures → remove from load balancer
```

`/ready` checks the database connection; `/health` is a simple alive check.

### IRSA (IAM Roles for Service Accounts)
Each service gets its own K8s ServiceAccount bound to an IAM role with **least-privilege** permissions:
- `risk-service-sa` → SQS publish (stop-loss, profit-lock queues only)
- `notification-service-sa` → SQS consume + SES send + SNS publish
- `data-validator-sa` → S3 read/write (market-data bucket only)

No long-lived AWS access keys anywhere in the cluster.

---

## 12. AWS Infrastructure

All provisioned via Terraform with modules for each component. State stored in S3 (versioned).

```
VPC (10.0.0.0/16)
├── Public Subnets  (3 AZs) → ALB, NAT Gateway
└── Private Subnets (3 AZs) → EKS nodes, RDS, ElastiCache

EKS: t3.medium nodes, Cluster Autoscaler, On-Demand (prod) + Spot (dev/staging)
RDS: PostgreSQL 15, Multi-AZ (prod), 7-day backup, PITR, KMS encryption
ElastiCache: Redis 7, TLS in transit
SQS: 6 FIFO queues + 6 DLQs, VPC Endpoint (traffic stays inside VPC)
ECR: 1 repo per service, scan on push, lifecycle policy (keep last 10 tagged)
S3: reports/, market-data/ (fallback cache), logs/, tf-state/
WAF: Rate limit 1000 req/5min per IP, AWS Managed Core Rule Set, SQLi/XSS blocking
Secrets Manager: one secret per env per credential type
CloudFront → Route53: edge caching for static assets, pass-through for /api/
```

---

## 13. Observability — Metrics, Traces, Logs

### Metrics (Prometheus + Grafana)
Every service exposes `/metrics`. Custom business metrics:
```python
STOP_LOSS_COUNTER   = Counter("swingedge_stop_loss_total", ..., ["ticker", "market"])
PROFIT_LOCK_COUNTER = Counter("swingedge_profit_lock_total", ..., ["threshold"])
ACTIVE_POSITIONS    = Gauge("swingedge_active_positions", ...)
RISK_EVAL_LATENCY   = Histogram("swingedge_risk_eval_seconds", ...)
```

Three Grafana dashboards:
1. **System Health** — pod status, HTTP error rate, P99 latency, circuit breaker states, pod restarts
2. **Business Metrics** — active positions, SL triggers/day, profit locks by threshold, SQS queue depth
3. **Batch Jobs** — last run time, success/failure rate (7-day), Celery queue depth

### Traces (OpenTelemetry → Jaeger)
One `init_tracing(service_name)` call per service auto-instruments FastAPI, SQLAlchemy, and outgoing HTTP calls. Every request, DB query, SQS publish/consume, and circuit breaker state change is traced. Trace IDs are injected into log lines for correlation.

### Logs (Fluent Bit → CloudWatch)
Structured JSON logs from every service:
```json
{
  "timestamp": "...", "level": "INFO", "service": "risk-service",
  "message": "Stop-loss triggered", "trace_id": "abc123...",
  "module": "week_rules", "ticker": "RELIANCE"
}
```
Fluent Bit runs as a DaemonSet. Log groups: `/swingedge/{service}`. 7-day retention (dev), 30-day (prod).

### Alerting
Alertmanager → PagerDuty for on-call routing. CloudWatch alarms for DLQ depth > 0, SL event spike, high error rate.

---

## 14. Secrets & Config Management

**Rule: Zero secrets in code, environment variables, or Docker images.**

| What | Where | How Accessed in K8s |
|---|---|---|
| DB passwords, API keys, JWT secret | AWS Secrets Manager | External Secrets Operator syncs to K8s Secret; refreshes hourly |
| Non-sensitive config (thresholds, schedules) | ConfigMap via Helm values | Mounted as env vars or volume |
| Local dev secrets | `.env.dev` (gitignored) | `docker-compose` env_file |

Terraform provisions Secrets Manager entries. ESO watches for changes and updates the K8s Secret automatically — no manual `kubectl` secret management needed.

---

## 15. Real-Time Updates — SSE

**Why SSE over WebSocket?** Risk events are one-directional (server → client). SSE is simpler, works over standard HTTP/1.1, and doesn't require a WebSocket upgrade — important for passing through Nginx and ALBs.

**How it works:**
1. `risk-service` maintains an in-memory list of SSE subscriber queues
2. Every time a risk rule fires (SL hit, profit lock, etc.), it calls `broadcast(event)`
3. `broadcast()` puts the event on every subscriber's async queue
4. The SSE endpoint streams these events as `data: {...}\n\n` to the browser
5. The React `useSSE` hook reconnects automatically after 3 seconds on connection loss
6. Nginx config: `proxy_buffering off` — critical; without this, Nginx buffers SSE and events arrive in batches

---

## 16. Distributed Tracing — OpenTelemetry + Jaeger

```python
# One call in each service's main.py — auto-instruments everything
init_tracing(service_name="risk-service", app=app)
```

What gets traced automatically:
- Every FastAPI HTTP request in and out
- Every SQLAlchemy database query (table, duration, rows)
- Every SQS publish and consume operation
- Every outgoing HTTP call (httpx auto-instrumentation)
- Circuit breaker state changes (manual spans)

**Jaeger deployed on K8s** with OTLP gRPC collector on port 4317. In production, backend is AWS OpenSearch for trace storage and querying.

---

## 17. Immutable Audit Log

Every trade action is recorded in `audit.audit_log`. The application write user has **INSERT only** — no UPDATE, no DELETE, ever.

```sql
-- Table is partitioned by month for query performance (pg_partman)
CREATE TABLE audit.audit_log (
    id UUID DEFAULT gen_random_uuid(),
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    service TEXT,       -- 'risk-service'
    actor TEXT,         -- 'system' or 'user:{id}'
    action TEXT,        -- EventType (e.g. 'STOP_LOSS_HIT')
    entity_type TEXT,   -- 'position'
    entity_id TEXT,
    before_json JSONB,  -- state before action
    after_json JSONB,   -- state after action
    trace_id TEXT,      -- links to Jaeger trace
    metadata_json JSONB
) PARTITION BY RANGE (occurred_at);

REVOKE UPDATE, DELETE ON audit.audit_log FROM swe_audit_writer;
```

Used for: position forensics, SEBI compliance review, debugging race conditions in rule evaluation.

---

## 18. Feature Flags

Stored in Redis. Toggled via Redis CLI or an admin endpoint — no redeploy needed.

```bash
redis-cli SET "flag:new_ocf_weight_v2" "true"
redis-cli SET "flag:enable_macro_auto_exit" "false"
```

Used to: gradually roll out new scoring formulas, swap data sources, enable/disable auto-exit logic during testing.

---

## 19. Contract Testing — Pact

**What is Pact?** Consumer-driven contract testing. The `scoring-service` (consumer) defines what it expects from `screening-service`'s (provider) API. The Pact broker stores this contract. Before any deployment, the provider must verify it still satisfies all consumer contracts. If `screening-service` changes its API in a breaking way, the Pact verification fails and the Jenkins build blocks.

**Why it matters here:** With 7+ services, integration tests alone can't catch API drift quickly enough. Pact catches breaking API changes before they reach staging.

---

## 20. Local Development Setup

```bash
# 1. Clone
git clone https://github.com/Manohar0441/DevOps_Project_Trading_System
cd DevOps_Project_Trading_System

# 2. Create local env file (never commit this)
cp .env.example .env.dev
# Set: DATABASE_URL, REDIS_URL, SQS_ENDPOINT_URL=http://localstack:4566

# 3. Start full local stack
docker-compose up --build

# Services available at:
#   Frontend:     http://localhost:8080
#   Scoring:      http://localhost:8000
#   Batch:        http://localhost:8001
#   Portfolio:    http://localhost:8003
#   Risk:         http://localhost:8004
#   Screening:    http://localhost:8005
#   Notification: http://localhost:8006
#   LocalStack:   http://localhost:4566

# 4. Run manual scoring pipeline (CLI)
python main.py MSFT --input-json inputs/MSFT.json --output-dir outputs/

# 5. Run tests
pytest tests/unit/ -v
pytest tests/integration/ -v --env=dev
```

---

## 21. Interview Q&A — Key Design Decisions

**Q: Why use SQS instead of calling notification-service directly from risk-service?**
A: Decoupling. `risk-service` is on the critical path — it runs every 30 minutes during market hours. If `notification-service` is slow or down, a synchronous call would block or fail the risk evaluation. SQS absorbs the load difference; `notification-service` can lag behind and catch up without any impact on risk evaluation.

**Q: Why one PostgreSQL schema per service instead of one DB per service?**
A: Cost and operational simplicity. A full DB per service means 7 RDS instances. Schema isolation gives the same logical separation (each service has its own tables and user) with one managed instance, one backup policy, one monitoring target.

**Q: Why RedBeat instead of default Celery Beat for scheduling?**
A: Default Celery Beat has a single-point-of-failure — it runs on one node and if that node dies, no jobs run until it's restarted. RedBeat stores the schedule in Redis, so any Celery worker can pick up the scheduler role. This gives HA scheduling without a dedicated scheduler pod.

**Q: How does the canary deployment work?**
A: NGINX Ingress supports traffic splitting via `canary-weight` annotations. We deploy the new version as a separate K8s Deployment with `canary.weight=10`. After 5 minutes, Jenkins queries Prometheus for error rate and P99 latency on canary pods. If both pass thresholds, traffic is shifted to 100% on the new version and the old Deployment is removed. If either fails, `helm rollback` restores the previous state.

**Q: What happens if ALL external data sources fail?**
A: The fallback chain in `data-validator-service` tries: primary (NSE/yfinance) → fallback-1 (Alpha Vantage/Screener.in) → fallback-2 (last-good S3 cache with `stale: true` flag). If S3 cache also fails, it raises `DataUnavailableError`, the batch job pauses, and an SNS alert is sent. No corrupt data enters the scoring pipeline.

**Q: How do you prevent duplicate job execution in Celery?**
A: Every job acquires a Redis lock with a unique key (`job:{name}:{date}:{slot}`), using `SET key value NX EX 3600` (set only if not exists, expire in 1 hour). If the lock already exists, the job logs a skip and returns. If the job fails, the lock is deleted immediately to allow a retry.

**Q: How are secrets managed? Where are they stored?**
A: Secrets live only in AWS Secrets Manager, never in code, environment variables, Docker images, or K8s YAML files. The External Secrets Operator runs in the cluster and syncs Secrets Manager values into K8s Secrets on a 1-hour cycle. Services reference secrets via `secretKeyRef` in their deployment manifests. Jenkins accesses AWS via an OIDC IAM role — no long-lived keys anywhere.

**Q: How does the audit log prevent tampering?**
A: The PostgreSQL user that the application uses for the audit schema has `INSERT` privilege only — `UPDATE` and `DELETE` are explicitly revoked. Monthly table partitioning (via `pg_partman`) means old partition files can also be archived to S3 and made immutable with S3 Object Lock if needed for compliance.

---

## Architecture Decision Summary

| Decision | Chosen Approach | Alternative Considered | Reason |
|---|---|---|---|
| Service communication | SQS async + HTTP sync | Kafka, RabbitMQ | SQS is managed, no cluster to operate; simpler for team of 2 |
| DB isolation | Schema per service (one RDS) | DB per service | Cost; one Multi-AZ instance vs seven |
| Scheduling HA | RedBeat (Redis) | Default Celery Beat | Eliminates scheduler SPOF |
| Canary deploys | NGINX Ingress weight | Argo Rollouts, Flagger | Lighter dependency; Jenkins can orchestrate it directly |
| Real-time UI | SSE | WebSocket | One-directional; simpler; works through all proxies |
| Secrets | AWS Secrets Manager + ESO | Vault, K8s Secrets directly | Native AWS; ESO gives auto-rotation support |
| Contract testing | Pact | None (rely on integration tests) | Catches API drift before staging; faster feedback |

---

*Built by Manohar — DevOps + Python microservices project for learning and interview preparation.*
