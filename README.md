# 📈 SwingEdge — Automated Swing Trading Strategy Platform
### Microservice Architecture | Event-Driven | DevOps | Docker | Kubernetes | Jenkins | AWS
> **System Version:** 3-Month Cycle, Dynamic Quarterly, India + USA
> **Team Size:** 2 Engineers | **Stack:** Python · React · PostgreSQL · Redis · SQS · AWS EKS

---

## 📌 Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture Diagram](#2-system-architecture-diagram)
3. [Microservices Breakdown](#3-microservices-breakdown)
4. [Repository & Folder Structure](#4-repository--folder-structure)
5. [Tech Stack](#5-tech-stack)
6. [Event-Driven Architecture](#6-event-driven-architecture)
7. [Database Architecture — Service Isolation](#7-database-architecture--service-isolation)
8. [Circuit Breakers & Resilience Patterns](#8-circuit-breakers--resilience-patterns)
9. [Distributed Tracing](#9-distributed-tracing)
10. [API Versioning Strategy](#10-api-versioning-strategy)
11. [Immutable Audit Log](#11-immutable-audit-log)
12. [Real-Time Updates — SSE & WebSocket](#12-real-time-updates--sse--websocket)
13. [Market Data Validation Pipeline](#13-market-data-validation-pipeline)
14. [DevOps Pipeline — Jenkins CI/CD](#14-devops-pipeline--jenkins-cicd)
15. [Docker Strategy](#15-docker-strategy)
16. [Kubernetes (K8s) on AWS EKS](#16-kubernetes-k8s-on-aws-eks)
17. [AWS Infrastructure Layout](#17-aws-infrastructure-layout)
18. [Secrets & Config Management](#18-secrets--config-management)
19. [Feature Flags](#19-feature-flags)
20. [Monitoring & Observability](#20-monitoring--observability)
21. [Graceful Shutdown & Pod Lifecycle](#21-graceful-shutdown--pod-lifecycle)
22. [Compliance & Audit (SEBI)](#22-compliance--audit-sebi)
23. [Timezone Handling](#23-timezone-handling)
24. [Contract Testing — Pact](#24-contract-testing--pact)
25. [RTO / RPO & Disaster Recovery](#25-rto--rpo--disaster-recovery)
26. [Team Responsibilities Split](#26-team-responsibilities-split)
27. [Sprint Plan — 16-Week Roadmap](#27-sprint-plan--16-week-roadmap)
28. [Environment Strategy](#28-environment-strategy)
29. [Naming Conventions & Standards](#29-naming-conventions--standards)
30. [Local Development Setup](#30-local-development-setup)
31. [Definition of Done](#31-definition-of-done)

---

## 1. Project Overview

SwingEdge is a **rules-based automated swing trading platform** that operationalises a disciplined quarterly trading framework for Indian (NSE/BSE) and US (NYSE/NASDAQ) equities. The system enforces strict, emotion-free trading logic through automated pipelines.

| Pillar | What the System Does |
|---|---|
| **Screening** | Filters stock universe by quarterly earnings momentum (Q_N > Q_N-1, ≥5% sequential EPS growth) |
| **Scoring** | Ranks stocks across 14 metrics from the Metrics Bible (growth, profitability, financial health, valuation) |
| **Portfolio Construction** | Allocates capital across top-conviction stocks; sector limits, position sizing, SL-aware |
| **Risk Management** | Enforces week-specific SL rules, profit-lock thresholds, portfolio heat limits in real-time |
| **Event Bus** | Async event dispatch for SL hits, profit locks, exit deadlines — no polling, no missed triggers |
| **Batch Execution** | HA-scheduled quarterly and monthly jobs via RedBeat + Celery |
| **Dashboard** | Real-time SSE-powered UI — trade tracker, checklists, cycle health, calendar |
| **Notifications** | Push alerts for every rule trigger via AWS SNS (SMS) + SES (email) |
| **Audit** | Immutable append-only audit log for every trade action — forensics and SEBI compliance |

The platform is built as **isolated microservices** (one schema per service), communicating via both **synchronous HTTP** and **asynchronous SQS events**, orchestrated on **AWS EKS**, deployed through a **Jenkins CI/CD pipeline** with canary releases, and fully containerised with **Docker**.

---

## 2. System Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                     │
│                                                                               │
│           ┌───────────────────────────────────────────┐                      │
│           │          React Frontend (SPA)              │                      │
│           │  Dashboard · Checklists · Real-time SSE    │                      │
│           └──────────────────┬────────────────────────┘                      │
└─────────────────────────────-┼────────────────────────────────────────────────┘
                               │ HTTPS / SSE
┌──────────────────────────────▼────────────────────────────────────────────────┐
│               AWS CloudFront → Route 53 → ALB → Nginx Ingress                 │
└──────────────────────────────┬────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────────────┐
│                     KUBERNETES CLUSTER (AWS EKS)                               │
│                                                                               │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ frontend   │  │ screening   │  │  scoring    │  │ portfolio   │          │
│  │ service    │  │ service     │  │  service    │  │ service     │          │
│  │ (Nginx)    │  │ (FastAPI)   │  │  (FastAPI)  │  │ (FastAPI)   │          │
│  └────────────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│                         │  ┌─────────────┘                 │                 │
│  ┌────────────┐  ┌──────▼──▼───┐  ┌─────────────┐  ┌──────▼──────┐          │
│  │notification│  │  risk       │  │  batch      │  │  data-      │          │
│  │ service    │  │  service    │  │  service    │  │  validator  │          │
│  │ (FastAPI)  │  │  (FastAPI)  │  │  (Celery+   │  │  service    │          │
│  └──────┬─────┘  └──────┬──────┘  │   RedBeat)  │  │  (FastAPI)  │          │
│         │               │         └─────────────┘  └─────────────┘          │
│  ┌──────▼───────────────▼────────────────────────────────────────────────┐   │
│  │                    EVENT BUS (AWS SQS — 6 Queues)                     │   │
│  │  stop-loss-events · profit-lock-events · exit-deadline-events         │   │
│  │  macro-override-events · screening-complete-events · audit-events     │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │               SHARED INFRASTRUCTURE (common library)                   │   │
│  │   ORM Models · Auth · Validators · Logging · Circuit Breakers          │   │
│  │   OpenTelemetry SDK · Audit Log Writer · SQS Publisher/Consumer        │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────────────┐
│                        DATA LAYER (Per-Service Isolation)                      │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL (AWS RDS Multi-AZ)                                           │ │
│  │  schema: screening | schema: scoring | schema: portfolio | schema: risk  │ │
│  │  schema: batch     | schema: notify  | schema: audit     | schema: flags │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌────────────────┐   ┌──────────────────────────┐   ┌─────────────────────┐ │
│  │ Redis 7        │   │ AWS S3                   │   │ AWS ElastiCache     │ │
│  │ (RedBeat       │   │ reports/ logs/ tf-state/ │   │ (app cache + rate   │ │
│  │  schedules +   │   │ market-data-cache/       │   │  limit counters)    │ │
│  │  feature flags)│   └──────────────────────────┘   └─────────────────────┘ │
│  └────────────────┘                                                           │
└───────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│                  EXTERNAL DATA SOURCES (with fallback chain)                  │
│                                                                               │
│  Primary          Fallback-1         Fallback-2        Validation             │
│  NSE API      →   Screener.in    →   Cached S3        Great Expectations      │
│  yfinance     →   Alpha Vantage  →   Cached S3        Schema + range checks   │
└───────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│               OBSERVABILITY (Metrics · Traces · Logs)                        │
│                                                                               │
│  Prometheus → Grafana         (metrics dashboards)                            │
│  OpenTelemetry → Jaeger       (distributed traces)                            │
│  Fluent Bit → CloudWatch Logs (structured JSON logs per service)              │
│  Alertmanager → SNS → PagerDuty (ops alerts)                                 │
└───────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────┐
│                   CI/CD (Jenkins — Canary Release Model)                      │
│                                                                               │
│  GitHub Push → Jenkins → Lint/Test/Pact → Docker Build → Trivy Scan          │
│  → ECR Push → Deploy Canary (10% traffic) → Metrics Gate                     │
│  → Promote to 100% OR Automatic Rollback                                      │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Microservices Breakdown

### 3.1 `frontend-service`
**Owner:** Developer | **Tech:** React 18, TypeScript, TailwindCSS, Vite, Nginx | **Port:** 3000

Serves the SPA. All communication goes through the API Gateway. Connects to `risk-service` via SSE for real-time event streaming. No direct database access.

**Key Pages/Features:**
- **Dashboard** — Active cycle PnL, portfolio heat, live SSE event feed
- **Stock Screener View** — 5-Query Research Protocol results
- **Trade Tracker** — All open/closed positions (entry, SL, targets, current P&L)
- **Checklist Module** — Interactive pre-entry checklist (all 10 items)
- **Cycle Review** — Quarterly/monthly review forms and learning log
- **Calendar** — Earnings dates, entry windows, exit deadlines (India + USA, timezone-aware)
- **Alerts Panel** — Real-time notification history
- **Audit Trail** — Immutable log view per position

---

### 3.2 `screening-service`
**Owner:** Developer | **Tech:** FastAPI, Python, Pandas | **Port:** 8001

Implements the 5-Query Research Protocol (Queries 1 and 2). Fetches from external data sources through the data-validator service.

**Key logic:**
- Apply quarterly momentum filter: Q_N > Q_N-1, minimum +5% sequential EPS growth
- Revenue growth ≥ 8% YoY, OCF > Net Income quality filter
- Output ranked list: top 25 India + top 25 USA candidates
- Sector strength analysis independently per market (no cross-market comparison)
- On completion, publishes `SCREENING_COMPLETE` event to SQS

**Endpoints (all under `/api/v1/`):**
```
GET  /api/v1/screen/india
GET  /api/v1/screen/usa
GET  /api/v1/screen/sectors/india
GET  /api/v1/screen/sectors/usa
POST /api/v1/screen/trigger
GET  /api/v1/health
GET  /api/v1/ready
GET  /metrics
```

**Circuit breaker:** Wraps all calls to `data-validator-service`. On open circuit, returns last cached S3 screening result with a `stale: true` flag.

---

### 3.3 `scoring-service`
**Owner:** Developer | **Tech:** FastAPI, Python, Pandas | **Port:** 8002

Implements the Metrics Bible (Section 10) and Pre-Entry Checklist (Section 5). Scores each candidate 0–100 across all metric categories. Subscribes to `SCREENING_COMPLETE` SQS events to auto-score new candidates.

**Scoring Dimensions:**

| Category | Metrics | Weight |
|---|---|---|
| Growth Quality | EPS Growth >10%, Revenue Growth >8%, OCF Growth >10%, OCF/NI >1.0 | 30% |
| Profitability | Operating Margin >15%, Net Margin >5%, ROIC >12%, ROE >12% | 25% |
| Financial Health | D/E <2.0, Current Ratio >1.5, Interest Coverage >3× | 20% |
| Valuation Sanity | P/E <Industry+30%, PEG <1.5, EV/EBITDA <15× | 15% |
| Technical / Momentum | RSI <70, 5–8% pullback from highs, volume trend, analyst upgrades | 10% |

**Endpoints (all under `/api/v1/`):**
```
POST /api/v1/score/stock
POST /api/v1/score/batch
GET  /api/v1/score/checklist/{ticker}
GET  /api/v1/score/exit-triggers
GET  /api/v1/score/history/{ticker}
GET  /api/v1/health
GET  /api/v1/ready
GET  /metrics
```

---

### 3.4 `portfolio-service`
**Owner:** Developer | **Tech:** FastAPI, Python | **Port:** 8003

Implements Query 5 of the Research Protocol — final capital allocation. Enforces all sector and sizing rules.

**Allocation rules enforced:**
- Minimum ₹5,000 per position
- No single sector > 60% of total capital
- India sector ≠ USA sector (correlation control)
- Stop-loss sizing: position size must respect 5–7% SL without breaching risk limits

**Endpoints (all under `/api/v1/`):**
```
POST /api/v1/portfolio/construct
GET  /api/v1/portfolio/active
GET  /api/v1/portfolio/history
PUT  /api/v1/portfolio/position/{id}
GET  /api/v1/portfolio/cycle-score
GET  /api/v1/portfolio/allocation-summary
GET  /api/v1/health
GET  /api/v1/ready
GET  /metrics
```

---

### 3.5 `risk-service`
**Owner:** Developer | **Tech:** FastAPI, Python, APScheduler | **Port:** 8004

The most critical service. Enforces Section 9 (Risk Management Framework) and Section 6 (3-Month Holding Cycle). Runs rule evaluation every 30 minutes during market hours. Publishes events to SQS on every rule trigger. Streams events to the frontend via SSE.

**Week-specific rules enforced:**

| Trigger | Action | Event Published |
|---|---|---|
| Position > +5% | Move SL to breakeven | `PROFIT_LOCK_5PCT` |
| Position > +8% | Move SL to +3% | `PROFIT_LOCK_8PCT` |
| Position > +10% | Book 40%, SL to +6% | `PROFIT_LOCK_10PCT` |
| Position > +12% | Book 30% more | `PROFIT_LOCK_12PCT` |
| Position > +15% | Exit or trail weekly | `EXIT_SIGNAL_15PCT` |
| SL hit at any point | Exit immediately | `STOP_LOSS_HIT` (CRITICAL) |
| Position < +5% after Week 6 | Exit signal | `DEAD_MONEY_EXIT` |
| Week 13 reached | Mandatory full exit | `MANDATORY_EXIT_DEADLINE` |
| Portfolio heat Month 1 > -3% | Alert | `PORTFOLIO_HEAT_BREACH` |
| Portfolio < prev month close (Month 2) | Alert | `PORTFOLIO_HEAT_BREACH` |
| Portfolio negative (Month 3) | Exit signal | `PORTFOLIO_HEAT_BREACH` |
| 2+ exit triggers simultaneously | Immediate exit | `MULTI_TRIGGER_EXIT` |

**Endpoints (all under `/api/v1/`):**
```
GET  /api/v1/risk/positions/status
POST /api/v1/risk/evaluate/{id}
GET  /api/v1/risk/portfolio-heat
GET  /api/v1/risk/exit-signals
GET  /api/v1/risk/week-rules/{id}
GET  /api/v1/risk/stream          ← SSE endpoint (persistent connection)
GET  /api/v1/health
GET  /api/v1/ready
GET  /metrics
```

---

### 3.6 `batch-service`
**Owner:** Developer | **Tech:** Python, Celery, RedBeat, Redis | **Port:** 8005

Runs all scheduled jobs. Uses **RedBeat** (Redis-backed) scheduler instead of the default Celery Beat to eliminate single-point-of-failure scheduling. Every job implements idempotency via a lock key in Redis.

**Scheduled Jobs:**

| Job | Schedule (IST) | Idempotency Key | Description |
|---|---|---|---|
| `quarterly_screen` | Start of quarter | `job:quarterly_screen:{quarter}` | Full screening pipeline |
| `monthly_review` | 1st of month, 8:00 AM | `job:monthly_review:{year}:{month}` | Portfolio health report |
| `daily_price_update` | Weekdays 6:30 AM | `job:price_update:{date}` | Fetch OHLC data (India + USA) |
| `risk_evaluation` | Every 30 min, market hours | `job:risk_eval:{date}:{slot}` | Risk rule evaluation for all positions |
| `exit_deadline_check` | Daily 7:00 AM | `job:exit_check:{date}` | Week 13 mandatory exit detector |
| `earnings_calendar_sync` | Sundays 9:00 AM | `job:earnings_sync:{week}` | Sync upcoming earnings dates |
| `profit_lock_trigger` | Every 1 hr, market hours | `job:profit_lock:{date}:{slot}` | Check profit-lock thresholds |
| `macro_monitor` | 1st of month, 7:00 AM | `job:macro:{year}:{month}` | Macro risk flag evaluation |
| `data_cache_warm` | Daily 5:45 AM | `job:cache_warm:{date}` | Pre-warm market data cache before market open |

**Idempotency pattern (applied to every job):**
```python
def run_with_idempotency(job_name: str, job_fn: callable, key: str):
    lock = redis_client.set(key, "running", nx=True, ex=3600)
    if not lock:
        logger.info(f"Job {job_name} already ran for key {key}, skipping")
        return
    try:
        job_fn()
        redis_client.set(key, "complete", ex=86400)
    except Exception as e:
        redis_client.delete(key)   # Allow retry on failure
        raise
```

**Endpoints:**
```
POST /api/v1/batch/run/{job_name}
GET  /api/v1/batch/jobs/status
GET  /api/v1/batch/logs/{job_name}
GET  /api/v1/batch/schedule
GET  /api/v1/health
GET  /api/v1/ready
GET  /metrics
```

---

### 3.7 `data-validator-service`
**Owner:** Developer | **Tech:** FastAPI, Python, Great Expectations | **Port:** 8007

A dedicated service that sits between all external data sources and internal services. Validates every data point before it enters the system. Implements the fallback chain.

**Validation checks per data point:**
- Schema validation (required fields present, correct types)
- Range checks (price > 0, EPS not null, revenue not negative)
- Staleness check (data timestamp within acceptable window)
- Split/dividend adjustment verification
- Outlier detection (>3σ from 90-day rolling average flags for review)

**Fallback chain:**
```
Primary source (NSE API / yfinance)
    → on failure/timeout → Fallback-1 (Alpha Vantage / Screener.in)
        → on failure → Fallback-2 (last-good S3 cache, marked stale)
            → on all failures → raise DataUnavailableError (job pauses, alert sent)
```

**Endpoints:**
```
POST /api/v1/validate/stock/{ticker}
POST /api/v1/validate/batch
GET  /api/v1/validate/source-health
GET  /api/v1/health
GET  /api/v1/ready
GET  /metrics
```

---

### 3.8 `notification-service`
**Owner:** Developer | **Tech:** FastAPI, Python, AWS SNS, AWS SES | **Port:** 8006

Consumes SQS events and dispatches notifications. Never called directly by other services — it is a pure SQS consumer. Deduplication via SQS message deduplication ID prevents double-alerts.

**Alert routing:**

| SQS Event | Channel | Priority | Template |
|---|---|---|---|
| `STOP_LOSS_HIT` | Email + SMS | CRITICAL | Stop-loss triggered on {ticker} at {price} |
| `MANDATORY_EXIT_DEADLINE` | Email + SMS | CRITICAL | Week 13 deadline: exit {ticker} today |
| `PROFIT_LOCK_10PCT` | Email | HIGH | Book 40% of {ticker} — hit +10% |
| `MULTI_TRIGGER_EXIT` | Email + SMS | HIGH | Multiple exit triggers — exit {ticker} immediately |
| `PORTFOLIO_HEAT_BREACH` | Email | HIGH | Portfolio heat limit breached |
| `SCREENING_COMPLETE` | Email | LOW | New cycle candidates available for review |
| `MONTHLY_REVIEW_DUE` | Email | MEDIUM | Monthly review due — login to review |

---

### 3.9 `common` (Shared Library)
**Owner:** Developer (DevOps input on config schemas) | **Type:** Internal Python package

Installed into all Python services via `pip install -e ./services/common`. Contains no business logic.

**Contains:**
- SQLAlchemy ORM base and per-schema session factories
- Pydantic v2 schemas (request/response validation)
- `SQSPublisher` and `SQSConsumer` base classes
- `CircuitBreaker` decorator (wraps `resilience4py`)
- OpenTelemetry SDK initialisation (one call, all services instrumented)
- `AuditLogWriter` — append-only writer to the audit schema
- Structured JSON logger (correlation ID, trace ID injected automatically)
- Config loader (env vars → Pydantic Settings, validated at startup)
- External API clients: `NSEClient`, `YFinanceClient`, `AlphaVantageClient`
- Constants: quarter date ranges, metric thresholds, rule values, IST/EST timezone objects
- Feature flag client (wraps Redis)

---

## 4. Repository & Folder Structure

```
swingEdge/
│
├── services/
│   ├── common/                              # Shared library — installed into all services
│   │   ├── common/
│   │   │   ├── models/                      # SQLAlchemy ORM models (per schema)
│   │   │   ├── schemas/                     # Pydantic v2 request/response schemas
│   │   │   ├── db/
│   │   │   │   ├── session.py               # Per-service session factories
│   │   │   │   └── migrations/              # Alembic env + per-schema version dirs
│   │   │   ├── events/
│   │   │   │   ├── publisher.py             # SQSPublisher base class
│   │   │   │   ├── consumer.py              # SQSConsumer base class
│   │   │   │   └── event_types.py           # Enum of all SQS event names
│   │   │   ├── resilience/
│   │   │   │   ├── circuit_breaker.py       # CircuitBreaker decorator
│   │   │   │   └── retry.py                 # Exponential backoff decorator
│   │   │   ├── tracing/
│   │   │   │   └── setup.py                 # OpenTelemetry SDK init
│   │   │   ├── audit/
│   │   │   │   └── writer.py                # AuditLogWriter (append-only)
│   │   │   ├── clients/
│   │   │   │   ├── nse.py                   # NSE API client
│   │   │   │   ├── yfinance_client.py       # yfinance wrapper
│   │   │   │   └── alpha_vantage.py         # Alpha Vantage client
│   │   │   ├── feature_flags.py             # Redis-backed feature flag client
│   │   │   ├── config.py                    # Pydantic Settings config loader
│   │   │   ├── logger.py                    # Structured JSON logger
│   │   │   └── constants.py                 # Thresholds, rule values, TZ objects
│   │   └── setup.py
│   │
│   ├── frontend_service/
│   │   ├── src/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── TradeTracker.tsx
│   │   │   │   ├── Checklist.tsx
│   │   │   │   ├── CycleReview.tsx
│   │   │   │   ├── Calendar.tsx
│   │   │   │   ├── AuditTrail.tsx
│   │   │   │   └── Alerts.tsx
│   │   │   ├── hooks/
│   │   │   │   └── useSSE.ts                # SSE connection hook
│   │   │   ├── store/
│   │   │   └── api/
│   │   ├── public/
│   │   ├── Dockerfile
│   │   ├── nginx.conf
│   │   └── package.json
│   │
│   ├── screening_service/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   └── v1/
│   │   │   │       └── routers/             # All endpoints under /api/v1/
│   │   │   ├── logic/
│   │   │   │   ├── screener.py
│   │   │   │   └── sector_ranker.py
│   │   │   ├── events/
│   │   │   │   └── publisher.py             # Publishes SCREENING_COMPLETE
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── contract/                    # Pact consumer contracts
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── scoring_service/                     # (Existing — restructure to match)
│   │   ├── app/
│   │   │   ├── api/v1/routers/
│   │   │   ├── logic/
│   │   │   │   ├── metrics_scorer.py
│   │   │   │   └── checklist_evaluator.py
│   │   │   ├── events/
│   │   │   │   └── consumer.py              # Consumes SCREENING_COMPLETE
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── contract/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── portfolio_service/
│   │   ├── app/
│   │   │   ├── api/v1/routers/
│   │   │   ├── logic/
│   │   │   │   └── allocator.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── contract/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── risk_service/
│   │   ├── app/
│   │   │   ├── api/v1/routers/
│   │   │   ├── logic/
│   │   │   │   ├── week_rules.py            # Week 1–13 rule engine
│   │   │   │   ├── profit_lock.py           # Profit-lock threshold checks
│   │   │   │   ├── portfolio_heat.py        # Monthly heat monitor
│   │   │   │   └── macro_monitor.py         # Macro risk flags
│   │   │   ├── events/
│   │   │   │   └── publisher.py             # Publishes all risk events
│   │   │   ├── sse/
│   │   │   │   └── stream.py                # SSE event stream endpoint
│   │   │   └── main.py
│   │   ├── tests/unit/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── data_validator_service/
│   │   ├── app/
│   │   │   ├── api/v1/routers/
│   │   │   ├── logic/
│   │   │   │   ├── validator.py             # Great Expectations checks
│   │   │   │   ├── fallback_chain.py        # Primary → Fallback1 → S3
│   │   │   │   └── outlier_detector.py      # 3σ anomaly detection
│   │   │   └── main.py
│   │   ├── tests/unit/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── batch_service/                       # (Existing — add RedBeat + idempotency)
│   │   ├── app/
│   │   │   ├── tasks/
│   │   │   │   ├── screening.py
│   │   │   │   ├── pricing.py
│   │   │   │   ├── risk_eval.py
│   │   │   │   ├── calendar_sync.py
│   │   │   │   └── macro.py
│   │   │   ├── scheduler.py                 # RedBeat schedule config
│   │   │   ├── idempotency.py               # Redis lock utility
│   │   │   └── main.py
│   │   ├── tests/unit/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── notification_service/
│       ├── app/
│       │   ├── api/v1/routers/
│       │   ├── channels/
│       │   │   ├── email.py                 # AWS SES
│       │   │   └── sms.py                   # AWS SNS
│       │   ├── events/
│       │   │   └── consumer.py              # SQS consumer — all queues
│       │   ├── templates/                   # Email HTML templates
│       │   └── main.py
│       ├── tests/unit/
│       ├── Dockerfile
│       └── requirements.txt
│
├── infra/                                   # DevOps — owned by DevOps engineer
│   ├── terraform/
│   │   ├── modules/
│   │   │   ├── eks/
│   │   │   ├── rds/
│   │   │   ├── elasticache/
│   │   │   ├── sqs/                         # SQS queues + DLQs
│   │   │   ├── s3/
│   │   │   ├── vpc/
│   │   │   ├── iam/
│   │   │   └── waf/                         # WAF rules for ALB
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   ├── staging/
│   │   │   └── prod/
│   │   └── main.tf
│   │
│   ├── helm/
│   │   └── swingEdge/
│   │       ├── Chart.yaml
│   │       ├── values.yaml
│   │       ├── values-dev.yaml
│   │       ├── values-staging.yaml
│   │       ├── values-prod.yaml
│   │       └── templates/
│   │           ├── *-deployment.yaml        # One per service
│   │           ├── *-service.yaml
│   │           ├── *-hpa.yaml
│   │           ├── *-pdb.yaml               # PodDisruptionBudget per service
│   │           ├── *-networkpolicy.yaml     # NetworkPolicy per service
│   │           ├── ingress.yaml
│   │           ├── configmaps.yaml
│   │           ├── externalsecrets.yaml     # AWS Secrets Manager sync
│   │           └── namespace-quota.yaml     # ResourceQuota per namespace
│   │
│   ├── jenkins/
│   │   ├── Jenkinsfile                      # Canary pipeline
│   │   ├── Jenkinsfile.hotfix
│   │   └── shared-library/
│   │       ├── vars/
│   │       │   ├── dockerBuild.groovy
│   │       │   ├── trivyScan.groovy
│   │       │   ├── helmDeploy.groovy
│   │       │   ├── canaryDeploy.groovy      # Canary logic
│   │       │   └── pactVerify.groovy        # Contract test step
│   │       └── src/
│   │
│   └── monitoring/
│       ├── prometheus/prometheus.yml
│       ├── grafana/dashboards/
│       │   ├── system-health.json
│       │   ├── business-metrics.json
│       │   └── batch-jobs.json
│       ├── jaeger/jaeger-values.yaml        # Jaeger Helm values
│       └── alertmanager/alertmanager.yml
│
├── config/
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
│
├── inputs/
├── outputs/
├── logs/
├── failed/
├── tests/
│   ├── integration/                         # Cross-service integration tests
│   ├── e2e/                                 # Full cycle E2E tests
│   └── contract/                            # Pact broker verification
├── stocks.txt
├── main.py
├── batchrunner.py
├── auto_peers_web.py
├── run_all.ps1
├── docker-compose.yml
├── docker-compose.dev.yml
├── .dockerignore
├── .gitignore
└── README.md
```

---

## 5. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18, TypeScript, TailwindCSS, Vite | SPA dashboard |
| **Backend Services** | Python 3.11, FastAPI, Pydantic v2 | All microservices |
| **Task Queue** | Celery + RedBeat | Async jobs, HA scheduling |
| **Message Broker / Cache** | Redis 7 (AWS ElastiCache) | Celery broker, RedBeat schedules, feature flags, cache |
| **Event Bus** | AWS SQS (6 queues + DLQs) | Async inter-service events |
| **Primary Database** | PostgreSQL 15 (AWS RDS Multi-AZ) | Per-service schema isolation |
| **ORM / Migrations** | SQLAlchemy + Alembic | DB access, schema versioning |
| **Resilience** | resilience4py | Circuit breakers |
| **Distributed Tracing** | OpenTelemetry SDK + Jaeger | Request traces across services |
| **Data Validation** | Great Expectations | Market data quality enforcement |
| **Contract Testing** | Pact | Service API contract verification |
| **Feature Flags** | Redis-backed (custom) | Safe rollout of logic changes |
| **API Gateway** | NGINX Ingress | Routing, rate limiting, TLS termination |
| **Containerisation** | Docker, Docker Compose | Local dev + build artefacts |
| **Orchestration** | Kubernetes (AWS EKS) | Production container management |
| **Helm** | Helm 3 | K8s package management |
| **CI/CD** | Jenkins (EC2) | Canary build-test-deploy pipeline |
| **Container Registry** | AWS ECR | Docker image storage + vulnerability scanning |
| **IaC** | Terraform | All AWS infra provisioning |
| **Cloud Provider** | AWS | EKS, RDS, ElastiCache, SQS, SES, SNS, S3, CloudFront, WAF |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |
| **Logging** | Fluent Bit → CloudWatch | Structured log aggregation |
| **Tracing** | OpenTelemetry → Jaeger | Distributed traces |
| **Ops Alerting** | Alertmanager + PagerDuty | On-call incident routing |
| **Secrets** | AWS Secrets Manager + External Secrets Operator | Credential management |
| **mTLS** | Istio service mesh (optional, Phase 2) | Internal service encryption |

---

## 6. Event-Driven Architecture

HTTP REST is used for synchronous request/response. AWS SQS is used for asynchronous, decoupled event dispatch. This pattern ensures that a slow or down consumer (e.g. `notification-service`) never blocks a producer (e.g. `risk-service`).

### SQS Queue Design

| Queue Name | Producer | Consumer(s) | DLQ | Retention |
|---|---|---|---|---|
| `swingedge-stop-loss-events` | risk-service | notification-service, audit-service | `...-dlq` | 4 days |
| `swingedge-profit-lock-events` | risk-service | notification-service, frontend (SSE relay) | `...-dlq` | 4 days |
| `swingedge-exit-deadline-events` | risk-service, batch-service | notification-service | `...-dlq` | 4 days |
| `swingedge-macro-override-events` | batch-service | risk-service, notification-service | `...-dlq` | 4 days |
| `swingedge-screening-complete-events` | screening-service | scoring-service | `...-dlq` | 4 days |
| `swingedge-audit-events` | all services | audit-writer (in common) | `...-dlq` | 14 days |

### Event Payload Schema

Every event follows this envelope. `payload` is event-specific.

```python
# services/common/common/events/event_types.py

from pydantic import BaseModel
from datetime import datetime
from enum import Enum
import uuid

class EventType(str, Enum):
    STOP_LOSS_HIT            = "STOP_LOSS_HIT"
    PROFIT_LOCK_5PCT         = "PROFIT_LOCK_5PCT"
    PROFIT_LOCK_8PCT         = "PROFIT_LOCK_8PCT"
    PROFIT_LOCK_10PCT        = "PROFIT_LOCK_10PCT"
    PROFIT_LOCK_12PCT        = "PROFIT_LOCK_12PCT"
    EXIT_SIGNAL_15PCT        = "EXIT_SIGNAL_15PCT"
    DEAD_MONEY_EXIT          = "DEAD_MONEY_EXIT"
    MANDATORY_EXIT_DEADLINE  = "MANDATORY_EXIT_DEADLINE"
    MULTI_TRIGGER_EXIT       = "MULTI_TRIGGER_EXIT"
    PORTFOLIO_HEAT_BREACH    = "PORTFOLIO_HEAT_BREACH"
    SCREENING_COMPLETE       = "SCREENING_COMPLETE"
    MACRO_OVERRIDE           = "MACRO_OVERRIDE"

class SwingEdgeEvent(BaseModel):
    event_id:    str       = str(uuid.uuid4())
    event_type:  EventType
    source:      str                           # originating service name
    trace_id:    str                           # OpenTelemetry trace ID
    occurred_at: datetime  = datetime.utcnow()
    payload:     dict
```

### SQS Publisher (base class in common)

```python
# services/common/common/events/publisher.py
import boto3, json
from .event_types import SwingEdgeEvent

class SQSPublisher:
    def __init__(self, queue_url: str):
        self._sqs   = boto3.client("sqs")
        self._queue = queue_url

    def publish(self, event: SwingEdgeEvent) -> None:
        self._sqs.send_message(
            QueueUrl              = self._queue,
            MessageBody           = event.model_dump_json(),
            MessageDeduplicationId= event.event_id,   # FIFO deduplication
            MessageGroupId        = event.event_type,
        )
```

### SQS Consumer (base class in common)

```python
# services/common/common/events/consumer.py
import boto3, json
from abc import ABC, abstractmethod

class SQSConsumer(ABC):
    def __init__(self, queue_url: str):
        self._sqs   = boto3.client("sqs")
        self._queue = queue_url

    def poll(self, max_messages: int = 10) -> None:
        response = self._sqs.receive_message(
            QueueUrl            = self._queue,
            MaxNumberOfMessages = max_messages,
            WaitTimeSeconds     = 20,        # Long-polling — reduces empty receives
        )
        for msg in response.get("Messages", []):
            body = json.loads(msg["Body"])
            self.handle(body)
            self._sqs.delete_message(
                QueueUrl      = self._queue,
                ReceiptHandle = msg["ReceiptHandle"],
            )

    @abstractmethod
    def handle(self, event: dict) -> None: ...
```

### Dead Letter Queue (DLQ) Policy

All queues have a corresponding DLQ. After **3 failed processing attempts**, the message is moved to the DLQ. A CloudWatch alarm fires when the DLQ depth exceeds 0. The ops team investigates and replays from the DLQ after fixing the root cause.

---

## 7. Database Architecture — Service Isolation

Every service owns its own PostgreSQL schema. No service may query another service's schema. Cross-service data is always fetched via API calls.

### Schema Map

| Service | Schema | Dedicated DB User | Tables (key ones) |
|---|---|---|---|
| screening-service | `screening` | `swe_screening` | `screen_runs`, `candidates`, `sector_rankings` |
| scoring-service | `scoring` | `swe_scoring` | `score_results`, `checklist_results`, `exit_triggers` |
| portfolio-service | `portfolio` | `swe_portfolio` | `cycles`, `positions`, `allocation_plans` |
| risk-service | `risk` | `swe_risk` | `risk_evaluations`, `sl_history`, `heat_log` |
| batch-service | `batch` | `swe_batch` | `job_runs`, `job_locks` |
| notification-service | `notify` | `swe_notify` | `notification_log`, `preferences` |
| data-validator | `validation` | `swe_validation` | `validation_runs`, `source_health` |
| audit | `audit` | `swe_audit_ro` (read-only) | `audit_log` (append-only, see Section 11) |

### Session Factory Pattern

Each service gets its own connection factory pointing at its schema:

```python
# services/common/common/db/session.py
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import os

def make_session_factory(schema: str):
    url    = os.environ["DATABASE_URL"]
    engine = create_engine(
        url,
        pool_size      = 10,
        max_overflow   = 20,
        pool_pre_ping  = True,     # Detect stale connections
        connect_args   = {"options": f"-csearch_path={schema},public"},
    )
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Each service calls:
SessionLocal = make_session_factory("scoring")
```

### Migration Strategy (Alembic — Per Schema)

```
services/common/common/db/migrations/
├── env.py                          # Multi-schema Alembic env
├── script.py.mako
└── versions/
    ├── screening/
    │   └── 001_initial_screening.py
    ├── scoring/
    │   └── 001_initial_scoring.py
    ├── portfolio/
    │   └── 001_initial_portfolio.py
    ├── risk/
    │   └── 001_initial_risk.py
    └── audit/
        └── 001_audit_log.py
```

Run migrations per schema in the Jenkins deploy stage:
```bash
alembic --name screening upgrade head
alembic --name scoring   upgrade head
# ... etc
```

### Database Credentials — One User Per Schema

```sql
-- Applied via Terraform (aws_db_instance + provisioner)
CREATE USER swe_screening  WITH PASSWORD '...';
CREATE USER swe_scoring    WITH PASSWORD '...';
-- ... etc

GRANT USAGE  ON SCHEMA screening TO swe_screening;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA screening TO swe_screening;

-- Audit user: read-only (write only via AuditLogWriter using a separate superuser)
CREATE USER swe_audit_ro WITH PASSWORD '...';
GRANT USAGE  ON SCHEMA audit TO swe_audit_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA audit TO swe_audit_ro;
```

---

## 8. Circuit Breakers & Resilience Patterns

Every external call (between services, and to external data APIs) is wrapped in a circuit breaker. This prevents one slow or failing dependency from cascading into a full system outage.

### Circuit Breaker Setup (resilience4py)

```python
# services/common/common/resilience/circuit_breaker.py
from resilience4py.circuitbreaker import CircuitBreaker
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: int = 30):
    """
    Decorator. Opens circuit after `failure_threshold` failures.
    Re-attempts after `recovery_timeout` seconds.
    """
    cb = CircuitBreaker(
        name              = name,
        failure_threshold = failure_threshold,
        recovery_timeout  = recovery_timeout,
    )
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return cb.call(fn, *args, **kwargs)
            except Exception as e:
                logger.warning(f"Circuit {name} triggered: {e}")
                raise
        return wrapper
    return decorator
```

### Usage in Services

```python
# In risk-service — calling notification-service via HTTP
from common.resilience.circuit_breaker import circuit_breaker
import httpx

@circuit_breaker(name="notification-service", failure_threshold=5, recovery_timeout=30)
def notify_stop_loss(position_id: str) -> None:
    # If this fails 5 times, circuit opens for 30s
    # Caller gets CircuitBreakerOpenError — handled gracefully
    httpx.post(f"{NOTIFY_URL}/api/v1/notify/send", json={"position_id": position_id}, timeout=3)
```

### Retry with Exponential Backoff

```python
# services/common/common/resilience/retry.py
import time, random, functools, logging

logger = logging.getLogger(__name__)

def with_retry(max_attempts: int = 3, base_delay: float = 1.0, exceptions=(Exception,)):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        raise
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {delay:.1f}s")
                    time.sleep(delay)
        return wrapper
    return decorator
```

### Circuit Breaker Map

| Caller Service | Called Service | Threshold | Recovery | Fallback |
|---|---|---|---|---|
| screening-service | data-validator-service | 5 | 30s | Last S3 cache (stale=True) |
| scoring-service | screening-service | 5 | 30s | Return cached score |
| portfolio-service | scoring-service | 3 | 20s | Halt — log error, alert |
| risk-service | notification-service | 5 | 30s | Publish to SQS (notify will catch it) |
| batch-service | risk-service | 3 | 60s | Skip evaluation, log, alert |
| data-validator | yfinance (external) | 3 | 60s | Alpha Vantage fallback |
| data-validator | Alpha Vantage (external) | 3 | 120s | S3 cache fallback |

---

## 9. Distributed Tracing

Every service is instrumented with OpenTelemetry. A single trace ID flows from the initial trigger (e.g. quarterly screen) through every downstream service call, so failures and latency can be pinpointed precisely.

### SDK Initialisation (one call in each service's `main.py`)

```python
# services/common/common/tracing/setup.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import os

def init_tracing(service_name: str, app=None) -> None:
    provider  = TracerProvider()
    exporter  = OTLPSpanExporter(endpoint=os.environ["JAEGER_OTLP_ENDPOINT"])
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI, SQLAlchemy, and outgoing HTTP calls
    if app:
        FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
```

```python
# In each service's main.py
from common.tracing.setup import init_tracing

app = FastAPI()
init_tracing(service_name="risk-service", app=app)
```

### What Gets Traced

- Every HTTP request in and out of each service
- Every database query (table, duration, row count)
- Every SQS publish and consume
- Every external API call (yfinance, NSE)
- Every circuit breaker state change

### Jaeger Deployment (K8s)

```yaml
# infra/monitoring/jaeger/jaeger-values.yaml
provisionDataStore:
  cassandra: false
  elasticsearch: false
storage:
  type: elasticsearch          # Use AWS OpenSearch in prod
allInOne:
  enabled: false
collector:
  enabled: true
query:
  enabled: true
  ingress:
    enabled: true
    hosts: ["jaeger.swingedge.internal"]
```

---

## 10. API Versioning Strategy

All service endpoints are prefixed with `/api/v1/`. This allows breaking changes to be introduced under `/api/v2/` without disrupting existing consumers.

### FastAPI Versioning Setup (applied to every service)

```python
# services/{service}/app/main.py
from fastapi import FastAPI
from app.api.v1 import router as v1_router

app = FastAPI(
    title       = "SwingEdge — Scoring Service",
    description = "Metrics Bible scorer and pre-entry checklist",
    version     = "1.0.0",
)

# v1 router — all endpoints under /api/v1/
app.include_router(v1_router, prefix="/api/v1")

# Non-versioned operational endpoints
@app.get("/health")  # K8s liveness probe
async def health(): return {"status": "ok"}

@app.get("/ready")   # K8s readiness probe
async def ready():
    # Check DB connection
    return {"status": "ready"}
```

### Versioning Rules

1. **Never break `/api/v1/` once deployed to production.** Any breaking change introduces `/api/v2/`.
2. **Non-breaking changes** (new optional fields, new endpoints) go into `/api/v1/` without version bump.
3. **v1 is maintained for a minimum of one full quarter** after v2 ships, to allow frontend migration.
4. **Deprecation header:** Services returning from a deprecated v1 endpoint include `Deprecation: true` and `Sunset: {date}` headers.
5. **Frontend API client** (`services/frontend_service/src/api/`) pins its version explicitly — never uses a dynamic version string.

---

## 11. Immutable Audit Log

Every trade action, rule trigger, and system decision is recorded in the `audit.audit_log` table. This table is append-only: the application user has only INSERT privilege. No UPDATE or DELETE is ever permitted.

### Schema

```sql
-- Applied via Alembic migration: audit/001_audit_log.py
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE audit.audit_log (
    id            UUID        NOT NULL DEFAULT gen_random_uuid(),
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service       TEXT        NOT NULL,   -- 'risk-service', 'batch-service', 'user'
    actor         TEXT        NOT NULL,   -- 'system', 'user:{id}', 'job:{name}'
    action        TEXT        NOT NULL,   -- EventType enum value
    entity_type   TEXT        NOT NULL,   -- 'position', 'cycle', 'allocation'
    entity_id     TEXT        NOT NULL,
    before_json   JSONB,                  -- State before change (null for creates)
    after_json    JSONB,                  -- State after change (null for deletes)
    trace_id      TEXT,                   -- OpenTelemetry trace ID for correlation
    metadata_json JSONB,                  -- Any additional context
    CONSTRAINT pk_audit_log PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);      -- Partition by month for performance

-- Partitions created automatically per month
CREATE TABLE audit.audit_log_2025_01 PARTITION OF audit.audit_log
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- (managed by pg_partman extension)

-- Immutability enforcement
REVOKE UPDATE, DELETE ON audit.audit_log FROM swe_audit_writer;
```

### AuditLogWriter (in common)

```python
# services/common/common/audit/writer.py
from sqlalchemy import text
from common.db.session import make_session_factory
from opentelemetry import trace

AuditSession = make_session_factory("audit")

class AuditLogWriter:
    def write(
        self,
        service:     str,
        actor:       str,
        action:      str,
        entity_type: str,
        entity_id:   str,
        before:      dict | None = None,
        after:       dict  | None = None,
        metadata:    dict  | None = None,
    ) -> None:
        span    = trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, "032x") if span else None

        with AuditSession() as session:
            session.execute(text("""
                INSERT INTO audit.audit_log
                  (service, actor, action, entity_type, entity_id,
                   before_json, after_json, trace_id, metadata_json)
                VALUES
                  (:service, :actor, :action, :entity_type, :entity_id,
                   :before, :after, :trace_id, :metadata)
            """), {
                "service": service, "actor": actor, "action": action,
                "entity_type": entity_type, "entity_id": entity_id,
                "before": before, "after": after, "trace_id": trace_id,
                "metadata": metadata,
            })
            session.commit()

# Singleton
audit = AuditLogWriter()
```

### Usage in risk-service

```python
from common.audit.writer import audit

def trigger_stop_loss(position):
    audit.write(
        service     = "risk-service",
        actor       = "system",
        action      = "STOP_LOSS_HIT",
        entity_type = "position",
        entity_id   = str(position.id),
        before      = {"price": position.entry_price, "sl": position.stop_loss},
        after       = {"exit_price": position.current_price, "pnl_pct": position.pnl_pct},
    )
```

---

## 12. Real-Time Updates — SSE & WebSocket

The frontend dashboard must reflect stop-loss hits, profit-lock triggers, and exit deadlines within seconds — not on the next polling cycle. Server-Sent Events (SSE) are used because they are one-directional (server to client), work over standard HTTP, and require no additional protocol overhead.

### SSE Stream Endpoint (risk-service)

```python
# services/risk_service/app/sse/stream.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from asyncio import Queue
import asyncio, json

router    = APIRouter()
listeners: list[Queue] = []

async def event_generator(queue: Queue):
    try:
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
    except asyncio.CancelledError:
        listeners.remove(queue)

@router.get("/api/v1/risk/stream")
async def stream_risk_events():
    queue = Queue()
    listeners.append(queue)
    return StreamingResponse(
        event_generator(queue),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",     # Disable Nginx buffering for SSE
        },
    )

def broadcast(event: dict) -> None:
    """Called by risk-service rule engine when any event fires."""
    for queue in listeners:
        queue.put_nowait(event)
```

### Frontend SSE Hook

```typescript
// services/frontend_service/src/hooks/useSSE.ts
import { useEffect, useRef } from "react";

export function useRiskStream(onEvent: (event: any) => void) {
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/api/v1/risk/stream");
    esRef.current = es;

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      onEvent(event);
    };

    es.onerror = () => {
      // Auto-reconnect after 3 seconds on connection loss
      es.close();
      setTimeout(() => { esRef.current = new EventSource("/api/v1/risk/stream"); }, 3000);
    };

    return () => es.close();
  }, []);
}
```

### Usage in Dashboard

```typescript
// Dashboard.tsx
useRiskStream((event) => {
  if (event.event_type === "STOP_LOSS_HIT") {
    showCriticalAlert(`Stop-loss triggered on ${event.payload.ticker}`);
  }
  if (event.event_type === "PROFIT_LOCK_10PCT") {
    showActionAlert(`Book 40% of ${event.payload.ticker} — hit +10%`);
  }
});
```

---

## 13. Market Data Validation Pipeline

Raw data from external sources contains nulls, stale prices, split-unadjusted values, and occasional API errors. The `data-validator-service` enforces quality before any data enters the scoring or screening logic.

### Validation Steps (Great Expectations)

```python
# services/data_validator_service/app/logic/validator.py
import great_expectations as ge
import pandas as pd

PRICE_DATA_EXPECTATIONS = [
    ("expect_column_values_to_not_be_null",    {"column": "close"}),
    ("expect_column_values_to_be_between",     {"column": "close",   "min_value": 0.01}),
    ("expect_column_values_to_be_between",     {"column": "volume",  "min_value": 0}),
    ("expect_column_values_to_not_be_null",    {"column": "date"}),
]

FUNDAMENTAL_EXPECTATIONS = [
    ("expect_column_values_to_not_be_null",    {"column": "eps"}),
    ("expect_column_values_to_not_be_null",    {"column": "revenue"}),
    ("expect_column_values_to_be_between",     {"column": "revenue", "min_value": 0}),
    ("expect_column_values_to_not_be_null",    {"column": "operating_cash_flow"}),
]

def validate_price_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
    ge_df    = ge.from_pandas(df)
    failures = []
    for expectation, kwargs in PRICE_DATA_EXPECTATIONS:
        result = getattr(ge_df, expectation)(**kwargs)
        if not result["success"]:
            failures.append(f"{expectation}: {result['result']}")
    return len(failures) == 0, failures
```

### Outlier Detection

```python
# services/data_validator_service/app/logic/outlier_detector.py
import numpy as np

def detect_price_outlier(current_price: float, rolling_mean: float, rolling_std: float) -> bool:
    """Flag data points more than 3 standard deviations from 90-day rolling average."""
    z_score = abs(current_price - rolling_mean) / rolling_std if rolling_std > 0 else 0
    return z_score > 3
```

### Fallback Chain Implementation

```python
# services/data_validator_service/app/logic/fallback_chain.py
from common.resilience.circuit_breaker import circuit_breaker
from common.resilience.retry import with_retry
import boto3, json

@circuit_breaker(name="yfinance", failure_threshold=3, recovery_timeout=60)
@with_retry(max_attempts=2)
def fetch_primary(ticker: str) -> dict:
    from common.clients.yfinance_client import YFinanceClient
    return YFinanceClient().fetch(ticker)

@circuit_breaker(name="alpha-vantage", failure_threshold=3, recovery_timeout=120)
@with_retry(max_attempts=2)
def fetch_fallback1(ticker: str) -> dict:
    from common.clients.alpha_vantage import AlphaVantageClient
    return AlphaVantageClient().fetch(ticker)

def fetch_fallback2_s3(ticker: str) -> dict:
    s3   = boto3.client("s3")
    obj  = s3.get_object(Bucket="swingedge-market-data", Key=f"cache/{ticker}.json")
    data = json.loads(obj["Body"].read())
    data["stale"] = True
    return data

def fetch_with_fallback(ticker: str) -> dict:
    for fetch_fn in [fetch_primary, fetch_fallback1, fetch_fallback2_s3]:
        try:
            data = fetch_fn(ticker)
            valid, errors = validate_price_data(data)
            if valid:
                return data
        except Exception as e:
            continue
    raise DataUnavailableError(f"All data sources failed for {ticker}")
```

---

## 14. DevOps Pipeline — Jenkins CI/CD

**Owner: DevOps Engineer**

### Canary Deployment Strategy

Production deploys use a canary model. New code is first exposed to 10% of traffic. Automated metric gates check for regressions. Only on gate pass does traffic shift to 100%.

```
New tag v1.2.0 pushed
      │
      ▼
Jenkins: Lint → Tests → Pact → Docker Build → Trivy Scan → Push ECR
      │
      ▼
Deploy Canary (10% traffic via NGINX Ingress weight)
      │
      ▼
Metric Gate (5 minutes):
  - Error rate < 1% on canary pods?
  - P99 latency < 500ms?
  - No circuit breakers opened?
  │
  ├── PASS → Promote: shift 100% traffic to new version
  └── FAIL → Automatic rollback: helm rollback, alert team
```

### Jenkinsfile (full pipeline)

```groovy
// infra/jenkins/Jenkinsfile

pipeline {
  agent { label 'docker-agent' }

  environment {
    AWS_REGION        = 'ap-south-1'
    ECR_REGISTRY      = "${AWS_ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com"
    APP_NAME          = 'swingedge'
    GIT_SHA_SHORT     = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
    CHANGED_SERVICES  = ''   // Populated in Detect Changes stage
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Detect Changed Services') {
      steps {
        script {
          CHANGED_SERVICES = sh(
            script: "git diff --name-only HEAD~1 HEAD | grep '^services/' | cut -d'/' -f2 | sort -u | tr '\\n' ','",
            returnStdout: true
          ).trim()
          echo "Changed services: ${CHANGED_SERVICES}"
        }
      }
    }

    stage('Lint & Static Analysis') {
      parallel {
        stage('Python') {
          steps {
            sh 'flake8 services/ --max-line-length=120'
            sh 'black --check services/'
            sh 'mypy services/ --ignore-missing-imports'
          }
        }
        stage('Frontend') {
          steps {
            dir('services/frontend_service') {
              sh 'npm ci && npm run lint'
            }
          }
        }
      }
    }

    stage('Unit Tests') {
      steps {
        script {
          CHANGED_SERVICES.split(',').each { svc ->
            if (svc && fileExists("services/${svc}/requirements.txt")) {
              sh """
                cd services/${svc}
                pip install -r requirements.txt -q
                pytest tests/unit/ -v --cov=app --cov-fail-under=70 \
                  --junitxml=test-results.xml
              """
            }
          }
        }
      }
      post {
        always { junit 'services/**/test-results.xml' }
      }
    }

    stage('Contract Tests (Pact)') {
      steps {
        sh '''
          cd tests/contract
          pytest -v --pact-broker-url=${PACT_BROKER_URL}
        '''
      }
    }

    stage('Docker Build') {
      steps {
        script {
          CHANGED_SERVICES.split(',').each { svc ->
            if (svc) {
              sh "docker build -t ${ECR_REGISTRY}/${svc}:${GIT_SHA_SHORT} services/${svc}/"
            }
          }
        }
      }
    }

    stage('Security Scan (Trivy)') {
      steps {
        script {
          CHANGED_SERVICES.split(',').each { svc ->
            if (svc) {
              sh """
                trivy image --exit-code 1 --severity CRITICAL \
                  ${ECR_REGISTRY}/${svc}:${GIT_SHA_SHORT}
              """
            }
          }
        }
      }
    }

    stage('Push to ECR') {
      steps {
        script {
          sh "aws ecr get-login-password | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
          CHANGED_SERVICES.split(',').each { svc ->
            if (svc) {
              sh "docker push ${ECR_REGISTRY}/${svc}:${GIT_SHA_SHORT}"
            }
          }
        }
      }
    }

    stage('Deploy to Dev') {
      steps {
        sh """
          helm upgrade --install swingedge-dev infra/helm/swingEdge/ \
            --namespace swingedge-dev \
            -f infra/helm/swingEdge/values-dev.yaml \
            --set imageTag=${GIT_SHA_SHORT} \
            --wait --timeout 5m
        """
        sh 'bash infra/scripts/smoke_test.sh dev'
      }
    }

    stage('Integration Tests') {
      steps {
        sh 'pytest tests/integration/ -v --env=dev'
      }
    }

    stage('Deploy Canary to Staging') {
      when { branch 'main' }
      steps {
        sh """
          helm upgrade --install swingedge-staging infra/helm/swingEdge/ \
            --namespace swingedge-staging \
            -f infra/helm/swingEdge/values-staging.yaml \
            --set imageTag=${GIT_SHA_SHORT} \
            --wait --timeout 5m
        """
        sh 'bash infra/scripts/smoke_test.sh staging'
      }
    }

    stage('Deploy Canary to Production') {
      when { tag 'v*' }
      steps {
        script {
          // Deploy canary at 10% traffic
          sh """
            helm upgrade --install swingedge-prod-canary infra/helm/swingEdge/ \
              --namespace swingedge-prod \
              -f infra/helm/swingEdge/values-prod.yaml \
              --set imageTag=${GIT_SHA_SHORT} \
              --set canary.enabled=true \
              --set canary.weight=10 \
              --wait --timeout 5m
          """

          // Metric gate — 5 minutes
          sleep(time: 5, unit: 'MINUTES')
          def gatePass = sh(
            script: 'bash infra/scripts/metric_gate.sh',
            returnStatus: true
          ) == 0

          if (gatePass) {
            echo "Metric gate PASSED — promoting canary to 100%"
            sh """
              helm upgrade swingedge-prod-canary infra/helm/swingEdge/ \
                --namespace swingedge-prod \
                -f infra/helm/swingEdge/values-prod.yaml \
                --set imageTag=${GIT_SHA_SHORT} \
                --set canary.enabled=false \
                --atomic --timeout 10m
            """
          } else {
            echo "Metric gate FAILED — rolling back"
            sh "helm rollback swingedge-prod-canary --namespace swingedge-prod"
            error("Canary metric gate failed — deployment rolled back")
          }
        }
      }
    }
  }

  post {
    success { notify('✅ Pipeline passed', env.TAG_NAME ?: env.BRANCH_NAME) }
    failure { notify('❌ Pipeline failed — rollback triggered', env.TAG_NAME ?: env.BRANCH_NAME) }
  }
}
```

### Branch Strategy

| Branch | Purpose | Auto-Deploy To |
|---|---|---|
| `feature/*` | New features | Dev (on PR merge) |
| `main` | Stable integration | Staging (canary) |
| `v*` tags (e.g. `v1.2.0`) | Production releases | Prod (canary → promote) |
| `hotfix/*` | Emergency fixes | Staging → Prod fast-track |

---

## 15. Docker Strategy

**Owner: DevOps Engineer**

### Python Service Dockerfile (multi-stage, non-root)

```dockerfile
# Multi-stage — builder installs deps, production image is lean
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
# Install into /install prefix (copied to production stage — no pip in prod image)
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim AS production
WORKDIR /app
# Copy installed packages from builder
COPY --from=builder /install /usr/local
# Copy shared library first (changes less often — better layer caching)
COPY services/common /app/common
RUN pip install --no-cache-dir -e /app/common
# Copy service code
COPY services/{service_name}/app /app
# Non-root user — security requirement
RUN useradd -m -u 1001 appuser && chown -R appuser /app
USER appuser
# Expose port
EXPOSE {PORT}
# Liveness check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:{PORT}/health || exit 1
# Graceful shutdown: uvicorn respects SIGTERM
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{PORT}", \
     "--workers", "2", "--timeout-graceful-shutdown", "30"]
```

### Frontend Dockerfile (React + Nginx)

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci --frozen-lockfile
COPY . .
ARG VITE_API_BASE=/api/v1
RUN VITE_API_BASE=${VITE_API_BASE} npm run build

FROM nginx:1.25-alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN addgroup -S nginx && adduser -S -G nginx nginx
EXPOSE 3000
HEALTHCHECK CMD curl -f http://localhost:3000/ || exit 1
```

### Nginx Config (handles SSE, SPA routing, compression)

```nginx
# services/frontend_service/nginx.conf
server {
    listen 3000;
    root  /usr/share/nginx/html;

    gzip on;
    gzip_types text/plain application/javascript application/json text/css;

    # SSE — disable buffering so events reach browser immediately
    location /api/v1/risk/stream {
        proxy_pass         http://risk-service:8004;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_buffering    off;
        proxy_cache        off;
        chunked_transfer_encoding on;
    }

    # API proxy to ingress
    location /api/ {
        proxy_pass http://api-gateway;
    }

    # SPA fallback — all unknown paths serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### Docker Compose (Local Full Stack)

```yaml
# docker-compose.yml
version: '3.9'

x-common-env: &common-env
  env_file: .env.dev
  depends_on:
    postgres: { condition: service_healthy }
    redis:    { condition: service_healthy }

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB:       swingedge
      POSTGRES_USER:     swe_admin
      POSTGRES_PASSWORD: local_dev_password
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "swe_admin"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  localstack:
    image: localstack/localstack:3
    ports: ["4566:4566"]
    environment:
      SERVICES: sqs,s3,ses,sns
    volumes: [localstack_data:/var/lib/localstack]

  frontend:       { build: ./services/frontend_service, ports: ["3000:3000"], <<: *common-env }
  screening:      { build: ./services/screening_service, ports: ["8001:8001"], <<: *common-env }
  scoring:        { build: ./services/scoring_service, ports: ["8002:8002"], <<: *common-env }
  portfolio:      { build: ./services/portfolio_service, ports: ["8003:8003"], <<: *common-env }
  risk:           { build: ./services/risk_service, ports: ["8004:8004"], <<: *common-env }
  batch:          { build: ./services/batch_service, ports: ["8005:8005"], <<: *common-env }
  notification:   { build: ./services/notification_service, ports: ["8006:8006"], <<: *common-env }
  data-validator: { build: ./services/data_validator_service, ports: ["8007:8007"], <<: *common-env }

  celery-worker:
    build: ./services/batch_service
    command: celery -A app.tasks worker --loglevel=info --concurrency=4
    <<: *common-env

  celery-beat:
    build: ./services/batch_service
    command: celery -A app.tasks beat -S redbeat.RedBeatScheduler --loglevel=info
    <<: *common-env

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports: ["16686:16686", "4317:4317"]   # 16686=UI, 4317=OTLP gRPC

volumes:
  postgres_data:
  localstack_data:
```

> **Note:** LocalStack simulates SQS, S3, SES, and SNS locally. Set `SQS_ENDPOINT_URL=http://localstack:4566` in `.env.dev`.

---

## 16. Kubernetes (K8s) on AWS EKS

**Owner: DevOps Engineer**

### Cluster Layout

```
AWS EKS Cluster: swingedge-prod
│
├── Namespace: swingedge-prod
│   ├── Deployments (one per service)
│   ├── Services (ClusterIP internal / LoadBalancer for ingress)
│   ├── HorizontalPodAutoscalers
│   ├── PodDisruptionBudgets         ← every service
│   ├── NetworkPolicies              ← zero-trust per service
│   ├── ResourceQuota
│   ├── ConfigMaps
│   └── ExternalSecrets (synced from AWS Secrets Manager)
│
├── Namespace: swingedge-dev
├── Namespace: swingedge-staging
│
├── Namespace: monitoring
│   ├── Prometheus
│   ├── Grafana
│   ├── Alertmanager
│   └── Jaeger
│
├── Namespace: ingress-nginx
│   └── NGINX Ingress Controller
│
└── Cluster-scoped
    ├── ClusterAutoscaler
    ├── ExternalSecretsOperator
    └── Fluent Bit DaemonSet (log shipping)
```

### PodDisruptionBudget (every service)

```yaml
# infra/helm/swingEdge/templates/risk-pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: risk-service-pdb
  namespace: {{ .Values.namespace }}
spec:
  minAvailable: 1           # At least 1 pod alive during node drains/upgrades
  selector:
    matchLabels:
      app: risk-service
```

### NetworkPolicy — Zero-Trust Per Service

```yaml
# infra/helm/swingEdge/templates/risk-networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: risk-service-netpol
  namespace: {{ .Values.namespace }}
spec:
  podSelector:
    matchLabels:
      app: risk-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Only accept traffic from ingress controller and portfolio-service
    - from:
        - podSelector: { matchLabels: { app: ingress-nginx } }
        - podSelector: { matchLabels: { app: portfolio-service } }
      ports:
        - protocol: TCP
          port: 8004
  egress:
    # Can only call: notification-service, postgres, redis, SQS (AWS)
    - to:
        - podSelector: { matchLabels: { app: notification-service } }
      ports: [{ port: 8006 }]
    - to:
        - podSelector: { matchLabels: { app: postgres } }
      ports: [{ port: 5432 }]
    - to:
        - podSelector: { matchLabels: { app: redis } }
      ports: [{ port: 6379 }]
    - to:           # AWS SQS (via VPC endpoint — CIDR of VPC endpoint)
        - ipBlock: { cidr: "10.0.0.0/8" }
      ports: [{ port: 443 }]
```

### HorizontalPodAutoscaler

```yaml
# infra/helm/swingEdge/templates/risk-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: risk-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: risk-service
  minReplicas: 2
  maxReplicas: 8
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
```

### ResourceQuota (per namespace)

```yaml
# infra/helm/swingEdge/templates/namespace-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: swingedge-prod-quota
  namespace: swingedge-prod
spec:
  hard:
    pods:               "50"
    requests.cpu:       "8"
    requests.memory:    "16Gi"
    limits.cpu:         "16"
    limits.memory:      "32Gi"
    persistentvolumeclaims: "10"
```

### Deployment Template (resource limits + pre-stop hook)

```yaml
# infra/helm/swingEdge/templates/risk-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: risk-service
  namespace: {{ .Values.namespace }}
spec:
  replicas: {{ .Values.riskService.replicas }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0     # Zero-downtime: always keep current count during rollout
      maxSurge: 1
  selector:
    matchLabels:
      app: risk-service
  template:
    metadata:
      labels:
        app: risk-service
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8004"
        prometheus.io/path: "/metrics"
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: risk-service
          image: {{ .Values.ecrRegistry }}/risk-service:{{ .Values.imageTag }}
          ports:
            - containerPort: 8004
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef: { name: swingedge-secrets, key: database-url }
            - name: REDIS_URL
              valueFrom:
                secretKeyRef: { name: swingedge-secrets, key: redis-url }
            - name: SQS_STOP_LOSS_QUEUE_URL
              valueFrom:
                secretKeyRef: { name: swingedge-secrets, key: sqs-stop-loss-url }
            - name: JAEGER_OTLP_ENDPOINT
              value: "http://jaeger-collector.monitoring:4317"
            - name: SERVICE_NAME
              value: "risk-service"
          resources:
            requests: { cpu: "250m", memory: "256Mi" }
            limits:   { cpu: "500m", memory: "512Mi" }
          lifecycle:
            preStop:
              exec:
                # Give in-flight requests 15s to complete before SIGTERM
                command: ["/bin/sh", "-c", "sleep 15"]
          livenessProbe:
            httpGet: { path: /health, port: 8004 }
            initialDelaySeconds: 20
            periodSeconds: 30
            failureThreshold: 3
          readinessProbe:
            httpGet: { path: /ready, port: 8004 }
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 2
```

---

## 17. AWS Infrastructure Layout

**Owner: DevOps Engineer (Terraform)**

```
AWS Account (ap-south-1 primary, us-east-1 DR)
│
├── VPC (10.0.0.0/16)
│   ├── Public Subnets  (3 AZs) → ALB, NAT Gateway
│   └── Private Subnets (3 AZs) → EKS nodes, RDS, ElastiCache, SQS VPC Endpoint
│
├── AWS EKS
│   ├── Managed Node Group: t3.medium × 3 (min) / × 10 (max) — On-Demand
│   ├── Spot Node Group:    t3.medium × 0 (min) / × 6 (max)  — dev/staging only
│   ├── Cluster Autoscaler
│   └── AWS Load Balancer Controller
│
├── AWS RDS (PostgreSQL 15)
│   ├── Instance: db.t3.medium (prod), db.t3.micro (dev/staging)
│   ├── Multi-AZ: Yes (prod) / No (dev/staging)
│   ├── Read Replica: 1 (prod — for reporting queries)
│   ├── Automated Backups: 7-day retention (prod), 1-day (dev)
│   ├── Point-in-Time Recovery: Enabled
│   ├── pg_partman extension: Enabled (audit log monthly partitions)
│   └── Encryption at rest: Yes (AWS KMS)
│
├── AWS ElastiCache (Redis 7)
│   ├── Cluster mode: Single node (dev), 2-node with replica (prod)
│   ├── Encryption in transit: Yes (TLS)
│   └── Uses: Celery broker, RedBeat schedule store, feature flags, app cache
│
├── AWS SQS (per queue)
│   ├── 6 standard queues + 6 DLQs
│   ├── FIFO queues (deduplication enabled)
│   ├── VPC Endpoint: Enabled (traffic stays inside VPC)
│   └── DLQ alarm: CloudWatch triggers on depth > 0
│
├── AWS ECR
│   ├── 1 repo per service: swingedge/{service-name}
│   ├── Image scanning on push: Enabled
│   └── Lifecycle policy: Keep last 10 tagged images, delete untagged > 1 day
│
├── AWS S3
│   ├── swingedge-reports/        → Quarterly PDF reports
│   ├── swingedge-market-data/    → Cached market data (fallback chain)
│   ├── swingedge-logs/           → Archived CloudWatch logs
│   └── swingedge-tf-state/       → Terraform remote state (versioning enabled)
│
├── AWS Secrets Manager
│   ├── swingedge/{env}/database-url
│   ├── swingedge/{env}/redis-url
│   ├── swingedge/{env}/alpha-vantage-key
│   ├── swingedge/{env}/nse-api-key
│   ├── swingedge/{env}/smtp-credentials
│   ├── swingedge/{env}/sqs-queue-urls   (JSON map of all queue URLs)
│   └── swingedge/{env}/jwt-secret
│
├── AWS WAF (attached to ALB)
│   ├── Rate limiting: 1000 req/5min per IP
│   ├── AWS Managed Rule: Core rule set
│   └── Block: known bad IPs, SQL injection, XSS
│
├── AWS CloudWatch
│   ├── Log groups: /swingedge/{service} (7-day retention dev, 30-day prod)
│   ├── Metric alarms: CPU, Error rate, Latency, SQS DLQ depth
│   ├── Dashboards: System health, Business metrics
│   └── Log Insights: Pre-built queries for trade forensics
│
├── AWS Route 53
│   └── app.swingedge.io → CloudFront → ALB
│
├── AWS CloudFront
│   ├── Static assets: long TTL (hashed filenames)
│   ├── API routes: no cache (pass-through)
│   └── Price class: 100 (India + US edge locations)
│
├── AWS SES
│   └── Transactional email (alerts, reports, cycle reviews)
│
├── AWS SNS
│   └── SMS (CRITICAL alerts: SL hit, mandatory exit, macro override)
│
├── AWS IAM
│   ├── EKS Node Role (EC2 SSM, ECR pull)
│   ├── Jenkins Deploy Role (OIDC — no long-lived keys)
│   ├── IRSA (IAM Roles for Service Accounts):
│   │   ├── risk-service-sa → SQS publish (stop-loss, profit-lock queues)
│   │   ├── screening-service-sa → SQS publish (screening-complete queue)
│   │   ├── notification-service-sa → SQS consume + SES send + SNS publish
│   │   ├── batch-service-sa → SQS publish (all queues) + S3 write (market-data)
│   │   └── data-validator-sa → S3 read/write (market-data cache)
│   └── RDS Schema Users (per service — least privilege)
│
└── Jenkins EC2
    ├── Instance: t3.medium
    ├── Docker, kubectl, helm, trivy installed
    ├── AWS CLI (via OIDC IAM Role — no keys stored on disk)
    └── Pact Broker (separate t3.small or use PactFlow)
```

---

## 18. Secrets & Config Management

**Owner: DevOps Engineer**

All secrets live in **AWS Secrets Manager** and are synced into Kubernetes Secrets by the **External Secrets Operator**.

```yaml
# infra/helm/swingEdge/templates/externalsecrets.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: swingedge-secrets
  namespace: {{ .Values.namespace }}
spec:
  refreshInterval: 1h          # Re-sync every hour
  secretStoreRef:
    name: aws-secretsmanager
    kind: ClusterSecretStore
  target:
    name: swingedge-secrets
    creationPolicy: Owner
  data:
    - secretKey: database-url
      remoteRef:
        key: swingedge/{{ .Values.env }}/database-url
    - secretKey: redis-url
      remoteRef:
        key: swingedge/{{ .Values.env }}/redis-url
    - secretKey: sqs-stop-loss-url
      remoteRef:
        key: swingedge/{{ .Values.env }}/sqs-queue-urls
        property: stop_loss
```

**Non-sensitive config** (feature flag defaults, metric thresholds, batch schedules) lives in `ConfigMaps` — managed via Helm `values.yaml` per environment.

**Local development** uses `.env.dev` (never committed — in `.gitignore`). SQS/S3/SES are replaced by LocalStack.

---

## 19. Feature Flags

New scoring logic, updated metric thresholds, and revised rule weights should never go live as instant full rollouts. Feature flags allow logic changes to be enabled progressively and rolled back in seconds without a redeploy.

### Redis-Backed Feature Flag Client

```python
# services/common/common/feature_flags.py
import redis, os, json
from functools import lru_cache

_redis = redis.from_url(os.environ["REDIS_URL"])

def is_enabled(flag: str, default: bool = False) -> bool:
    """
    Check if a feature flag is enabled.
    Flags are set via Redis CLI or an admin endpoint.
    Example: redis-cli SET "flag:new_ocf_weight_v2" "true"
    """
    val = _redis.get(f"flag:{flag}")
    if val is None:
        return default
    return val.decode().lower() == "true"

def get_flag_value(flag: str, default) -> any:
    """For flags that carry a value (e.g. metric thresholds)."""
    val = _redis.get(f"flag:{flag}")
    if val is None:
        return default
    return json.loads(val.decode())
```

### Usage in scoring-service

```python
# Gradually roll out new OCF weighting formula
from common.feature_flags import is_enabled, get_flag_value

def calculate_growth_score(stock: StockData) -> float:
    if is_enabled("new_ocf_weight_v2"):
        # New formula — enabled for testing
        ocf_weight = get_flag_value("ocf_weight", default=0.30)
    else:
        # Current formula — safe default
        ocf_weight = 0.25
    return compute_score(stock, ocf_weight=ocf_weight)
```

### Defined Flags

| Flag | Default | Purpose |
|---|---|---|
| `new_ocf_weight_v2` | false | Updated OCF scoring formula |
| `use_alpha_vantage_primary` | false | Swap yfinance for Alpha Vantage as primary |
| `enable_macro_auto_exit` | false | Macro override auto-exits positions (vs alert-only) |
| `quarterly_screen_usa_only` | false | Limit screen to USA stocks only (testing) |
| `sse_broadcast_all_events` | true | Broadcast all risk events to SSE stream |

---

## 20. Monitoring & Observability

**Owner: DevOps Engineer**

Three pillars: **metrics** (Prometheus + Grafana), **traces** (OpenTelemetry + Jaeger), **logs** (Fluent Bit + CloudWatch).

### Service Metrics (Prometheus)

Every service exposes `/metrics`. Key custom metrics beyond default FastAPI/uvicorn metrics:

```python
# services/risk_service/app/main.py
from prometheus_client import Counter, Histogram, Gauge

STOP_LOSS_COUNTER   = Counter("swingedge_stop_loss_total",   "Total stop-loss triggers", ["ticker", "market"])
PROFIT_LOCK_COUNTER = Counter("swingedge_profit_lock_total", "Total profit-lock actions", ["threshold"])
ACTIVE_POSITIONS    = Gauge("swingedge_active_positions",    "Current open positions")
RISK_EVAL_LATENCY   = Histogram("swingedge_risk_eval_seconds", "Risk evaluation duration")
```

### Grafana Dashboards

**System Health Dashboard:**
- Pod status grid (green/red per service per replica)
- HTTP request rate, error rate (4xx/5xx), P99 latency per service
- Circuit breaker state per service pair
- Pod restart count (last 1 hour)

**Business Metrics Dashboard:**
- Active positions (open, at-target, at-risk)
- Stop-loss triggers per day
- Profit-lock triggers per threshold (+5%, +8%, +10%, +12%, +15%)
- Screening run latency
- Scoring throughput (stocks/minute)
- SQS queue depth per queue
- SQS DLQ depth (should always be 0)

**Batch Jobs Dashboard:**
- Last run time per job
- Job success/failure rate (7-day view)
- RedBeat schedule alignment vs actual run times
- Celery worker queue depth

### Structured JSON Logging

```python
# services/common/common/logger.py
import logging, json, sys
from opentelemetry import trace

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span     = trace.get_current_span()
        trace_id = format(span.get_span_context().trace_id, "032x") \
                   if span and span.get_span_context().is_valid else None
        return json.dumps({
            "timestamp":  self.formatTime(record),
            "level":      record.levelname,
            "service":    record.name,
            "message":    record.getMessage(),
            "trace_id":   trace_id,
            "module":     record.module,
            "func":       record.funcName,
            **(record.__dict__.get("extra", {})),
        })

def get_logger(name: str) -> logging.Logger:
    logger    = logging.getLogger(name)
    handler   = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

### Alerting Rules

| Alert | Condition | Severity | Destination |
|---|---|---|---|
| Pod crash loop | Restarts > 3 in 5 min | P1 | PagerDuty → On-call |
| API error rate | >5% 5xx over 2 min | P1 | PagerDuty |
| SQS DLQ depth > 0 | Any DLQ receives message | P1 | PagerDuty + Slack |
| RDS CPU > 80% | 5-min sustained | P2 | Slack |
| Celery queue > 100 | Queue depth > 100 | P2 | Slack |
| Circuit breaker opened | Any CB state change | P2 | Slack |
| Stop-loss triggered | risk-service event | — | Email + SMS to trader |
| Mandatory exit deadline | batch-service event | — | Email + SMS to trader |
| Jenkins pipeline failure | Any stage failure | P2 | Slack + Email to team |

---

## 21. Graceful Shutdown & Pod Lifecycle

When Kubernetes terminates a pod (node drain, rolling update, scale-down), it sends `SIGTERM`. Without handling, in-flight requests are dropped, open DB transactions are aborted, and Celery tasks may run twice on restart.

### FastAPI Graceful Shutdown

```python
# In every service's main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await db_engine.connect()
    await redis_client.ping()
    yield
    # --- Shutdown (on SIGTERM) ---
    # uvicorn --timeout-graceful-shutdown 30 gives 30s for in-flight requests
    await db_engine.dispose()
    await redis_client.aclose()

app = FastAPI(lifespan=lifespan)
```

### Celery Graceful Shutdown

```python
# services/batch_service/app/tasks/__init__.py
from celery.signals import worker_shutdown

@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    # Celery's --timeout=30 allows current tasks to finish
    # This hook runs after all tasks complete or timeout
    db_session.close()
    logger.info("Celery worker shut down cleanly")
```

### Kubernetes Pre-Stop Hook (in every Deployment)

```yaml
lifecycle:
  preStop:
    exec:
      # Wait 15s after SIGTERM before pod is removed from Service endpoints.
      # This ensures the load balancer stops routing new requests first,
      # then uvicorn's 30s graceful window handles in-flight ones.
      command: ["/bin/sh", "-c", "sleep 15"]
```

**Shutdown sequence timeline:**
```
t=0   Kubernetes removes pod from Service endpoints (no new traffic)
t=0   preStop hook runs: sleep 15s
t=15  SIGTERM sent to uvicorn
t=15  uvicorn begins 30s graceful shutdown window (finishes in-flight requests)
t=45  All connections closed, pod terminates cleanly
t=60  terminationGracePeriodSeconds boundary — pod force-killed if still running
```

---

## 22. Compliance & Audit (SEBI)

Automated trading systems operating in Indian markets must maintain verifiable audit trails. The following measures ensure the system is defensible under a SEBI review.

### Requirements Addressed

| Requirement | Implementation |
|---|---|
| Complete trade action log | Immutable `audit.audit_log` table (Section 11) — every action recorded |
| Timestamp accuracy | All timestamps in `TIMESTAMPTZ` (UTC), displayed in IST in UI |
| System-generated vs user-initiated separation | `actor` field distinguishes `system`, `user:{id}`, `job:{name}` |
| No modification of records | `REVOKE UPDATE, DELETE` on `audit.audit_log` for all app users |
| Traceability across services | OpenTelemetry `trace_id` in every audit record |
| Data retention | Audit log retained minimum 5 years (S3 archive after 1 year, 90-day on RDS) |
| Access logging | All audit table reads logged in CloudWatch (RDS Enhanced Monitoring) |
| Broker API integration | Each trade entry/exit records the broker order ID in `metadata_json` |

### Audit Retention Strategy

```
0–12 months  : Live in PostgreSQL audit schema (fast queries, monthly partitions)
12–60 months : Archived to S3 (swingedge-audit-archive/, Parquet format)
60+ months   : S3 Glacier (cost-efficient cold storage, 1-day retrieval SLA)
```

### SEBI-Relevant Audit Queries

```sql
-- Full history of all actions on a position
SELECT occurred_at, actor, action, before_json, after_json, trace_id
FROM audit.audit_log
WHERE entity_type = 'position' AND entity_id = :position_id
ORDER BY occurred_at ASC;

-- All stop-loss triggers in a quarter
SELECT occurred_at, entity_id, after_json->>'ticker' AS ticker,
       after_json->>'pnl_pct' AS pnl_pct
FROM audit.audit_log
WHERE action = 'STOP_LOSS_HIT'
  AND occurred_at BETWEEN :quarter_start AND :quarter_end;
```

---

## 23. Timezone Handling

India (IST = UTC+5:30) and USA (EST = UTC-5, EDT = UTC-4) operate in different timezones. All time logic must be explicit — no naive datetime objects anywhere in the codebase.

### Constants (in common)

```python
# services/common/common/constants.py
import pytz
from datetime import time

IST = pytz.timezone("Asia/Kolkata")
EST = pytz.timezone("America/New_York")
UTC = pytz.utc

# Market hours — all stored as UTC-aware times
INDIA_MARKET_OPEN_IST  = time(9, 15)    # 09:15 IST
INDIA_MARKET_CLOSE_IST = time(15, 30)   # 15:30 IST

USA_MARKET_OPEN_EST    = time(9, 30)    # 09:30 EST/EDT
USA_MARKET_CLOSE_EST   = time(16, 0)    # 16:00 EST/EDT

def is_india_market_open() -> bool:
    now_ist = datetime.now(IST).time()
    return INDIA_MARKET_OPEN_IST <= now_ist <= INDIA_MARKET_CLOSE_IST \
           and datetime.now(IST).weekday() < 5

def is_usa_market_open() -> bool:
    now_est = datetime.now(EST).time()
    return USA_MARKET_OPEN_EST <= now_est <= USA_MARKET_CLOSE_EST \
           and datetime.now(EST).weekday() < 5
```

### Celery Beat / RedBeat Schedule (timezone-explicit)

```python
# services/batch_service/app/scheduler.py
from celery.schedules import crontab
from common.constants import IST

beat_schedule = {
    "daily-price-update-india": {
        "task": "app.tasks.pricing.update_india_prices",
        # 06:30 IST = 01:00 UTC
        "schedule": crontab(hour=1, minute=0),
        "options": {"timezone": "UTC"},   # Always schedule in UTC
    },
    "daily-price-update-usa": {
        "task": "app.tasks.pricing.update_usa_prices",
        # 17:00 EST = 22:00 UTC (21:00 during EDT — handled by DST-aware cron)
        "schedule": crontab(hour=22, minute=0),
        "options": {"timezone": "UTC"},
    },
    "risk-evaluation": {
        "task": "app.tasks.risk_eval.run",
        # Every 30 min during India market hours (03:45–10:00 UTC) + USA (14:30–21:00 UTC)
        "schedule": crontab(minute="*/30", hour="3-10,14-21"),
        "options": {"timezone": "UTC"},
    },
}
```

### Database — All timestamps in UTC

```python
# All ORM models use timezone-aware UTC timestamps
from sqlalchemy import DateTime
from sqlalchemy.sql import func

class Position(Base):
    entry_date = Column(DateTime(timezone=True), nullable=False)
    exit_date  = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Frontend — Display in User's Timezone

```typescript
// All timestamps from API are UTC ISO strings
// Display in IST for India-focused dashboard
const toIST = (utcString: string) =>
  new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(utcString));
```

---

## 24. Contract Testing — Pact

Unit tests verify that individual services work. Contract tests verify that services agree on the shape of data they exchange. Without contract tests, a change to the scoring-service response schema silently breaks the portfolio-service.

### Setup

```bash
# Pact Broker runs as a separate service (or use PactFlow SaaS)
# Local: docker run -p 9292:9292 pactfoundation/pact-broker

pip install pact-python
```

### Consumer Contract (portfolio-service defines what it needs from scoring-service)

```python
# services/portfolio_service/tests/contract/test_scoring_contract.py
import pytest
from pact import Consumer, Provider

pact = Consumer("portfolio-service").has_pact_with(
    Provider("scoring-service"),
    pact_dir="./pacts",
    publish_to_broker=True,
    broker_base_url="http://pact-broker:9292",
)

def test_get_score_for_ticker():
    expected = {
        "ticker":             "RELIANCE.NS",
        "total_score":        78.5,
        "growth_score":       82.0,
        "checklist_passed":   True,
        "exit_triggers":      [],
        "scored_at":          pact.like("2025-01-15T09:00:00Z"),
    }

    with pact:
        pact.given("RELIANCE.NS has a valid score").upon_receiving(
            "a request for RELIANCE.NS score"
        ).with_request(
            method="GET", path="/api/v1/score/stock/RELIANCE.NS"
        ).will_respond_with(
            status=200, body=expected
        )
        # Actual call to the mock provider
        result = scoring_client.get_score("RELIANCE.NS")
        assert result["checklist_passed"] is True
```

### Provider Verification (scoring-service verifies it satisfies the contract)

```python
# services/scoring_service/tests/contract/test_scoring_provider.py
import pytest
from pact import Verifier

def test_scoring_service_satisfies_contracts():
    verifier = Verifier(
        provider="scoring-service",
        provider_base_url="http://localhost:8002",
    )
    output, _ = verifier.verify_pacts(
        broker_url                = "http://pact-broker:9292",
        publish_verification_results = True,
    )
    assert output == 0, "Scoring-service broke a consumer contract"
```

### In Jenkins Pipeline

The `Contract Tests (Pact)` stage (Section 14) runs provider verification against all published consumer contracts. A broken contract fails the pipeline before any deployment.

---

## 25. RTO / RPO & Disaster Recovery

### Definitions

| Term | Target | Meaning |
|---|---|---|
| **RTO** (Recovery Time Objective) | < 1 hour | Maximum time system can be down before trader is impacted |
| **RPO** (Recovery Point Objective) | < 15 minutes | Maximum data loss acceptable (most recent 15 min of trade events) |

### Backup Strategy

| Data Store | Backup Method | Frequency | Retention | Recovery |
|---|---|---|---|---|
| PostgreSQL (RDS) | Automated RDS snapshots | Daily + 5-min transaction log shipping | 7 days (prod) | Point-in-time restore to any minute |
| Redis (ElastiCache) | RDB snapshots to S3 | Every 6 hours | 3 days | Restore from snapshot (RedBeat schedules survive in RDB) |
| S3 buckets | Versioning enabled | On every write | 90 days (market-data) | Restore previous version |
| Terraform state | S3 backend + versioning | On every apply | 30 versions | Roll back via `terraform apply` from previous state |
| Secrets Manager | AWS-managed replication | Continuous | N/A | Multi-AZ by default |

### Failure Scenarios & Recovery

| Scenario | Impact | Recovery Steps | Expected RTO |
|---|---|---|---|
| **Single EKS pod crash** | One service replica down | K8s restarts pod automatically (liveness probe) | < 1 minute |
| **Entire node failure** | Multiple pods evicted | Cluster Autoscaler provisions replacement node; pods reschedule | < 5 minutes |
| **RDS primary failure** | DB unavailable | RDS Multi-AZ auto-promotes standby | < 2 minutes |
| **Redis failure** | Cache + RedBeat loss | ElastiCache replica promoted; RedBeat re-reads schedule from RDB | < 3 minutes |
| **SQS queue failure** | Events not delivered | AWS-managed; messages retained for 4 days; reprocess from DLQ | < 15 minutes |
| **Full AZ failure** | ~30% of capacity lost | Multi-AZ: EKS, RDS, ElastiCache all span AZs — automatic failover | < 10 minutes |
| **Full region failure** | All services down | Manual failover to us-east-1 DR environment (Terraform apply from backup state) | < 1 hour |
| **Jenkins failure** | CI/CD unavailable | Redeploy Jenkins from AMI snapshot or Terraform; last deploy still running in prod | < 30 minutes |

### DR Runbook (Region Failover)

```bash
# Step 1: Restore RDS from latest snapshot in us-east-1
aws rds restore-db-instance-to-point-in-time \
  --target-db-instance-identifier swingedge-dr \
  --source-db-instance-identifier swingedge-prod \
  --restore-time $(date -u -d "5 minutes ago" +%Y-%m-%dT%H:%M:%SZ) \
  --region us-east-1

# Step 2: Apply Terraform DR environment
cd infra/terraform/environments/dr
terraform apply -var="region=us-east-1" -var="db_endpoint=<restored-endpoint>"

# Step 3: Update Route 53 to point to DR ALB
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID \
  --change-batch file://dr-dns-failover.json

# Step 4: Verify health
bash infra/scripts/smoke_test.sh dr
```

---

## 26. Team Responsibilities Split

### 👨‍💻 Developer — Backend + Frontend

**Services:** `frontend_service`, `screening_service`, `scoring_service`, `portfolio_service`, `risk_service`, `batch_service`, `notification_service`, `data_validator_service`, `common`

**Deliverables per service:**
- REST API endpoints versioned under `/api/v1/`
- SQS event publisher or consumer as applicable (using `common` base classes)
- SQLAlchemy models + Alembic migrations in own schema
- Unit tests ≥ 70% coverage
- Pact consumer contracts where the service calls another
- Pact provider verification where the service is called by others
- Dockerfile (multi-stage, non-root, `/health` + `/ready` endpoints, `/metrics`)
- Feature flag usage for any logic that should be toggle-able
- Audit log writes on all state-changing operations (using `AuditLogWriter`)
- `.env.example` documenting all required environment variables
- OpenAPI docs auto-generated at `/docs`

**Standards to follow:**
- No hardcoded secrets — all from `os.environ`
- All timestamps `TIMESTAMPTZ` UTC in DB, displayed IST/EST in UI
- All external calls wrapped in circuit breaker
- All batch operations idempotent
- Graceful shutdown in every FastAPI `lifespan` context
- `trace_id` forwarded in every outgoing HTTP call header

---

### ⚙️ DevOps Engineer (You) — Infrastructure + CI/CD

| Area | Deliverable |
|---|---|
| **Terraform** | VPC, EKS, RDS (multi-AZ), ElastiCache, SQS + DLQs, S3, ECR, IAM (IRSA per service), Secrets Manager, WAF, CloudFront, Route 53 |
| **Jenkins** | EC2 instance, GitHub webhook, Jenkinsfile (canary pipeline), shared library (dockerBuild, trivyScan, helmDeploy, canaryDeploy, pactVerify) |
| **Docker** | Review all Dockerfiles, enforce multi-stage + non-root, ECR lifecycle policies |
| **Kubernetes** | EKS bootstrap, Helm umbrella chart, per-service Deployment + Service + HPA + PDB + NetworkPolicy, ResourceQuota per namespace, Cluster Autoscaler |
| **External Secrets** | External Secrets Operator, ClusterSecretStore, ExternalSecret per service |
| **Canary** | NGINX Ingress weight-based routing, metric gate script (`metric_gate.sh`) |
| **Monitoring** | Prometheus + Grafana (3 dashboards), Jaeger Helm deploy, Alertmanager → PagerDuty + Slack, Fluent Bit DaemonSet → CloudWatch |
| **LocalStack** | Configure for local dev (SQS, S3, SES, SNS) — document setup in Section 30 |
| **RedBeat** | Verify Redis persistence (RDB enabled) so RedBeat survives restarts |
| **Pact Broker** | Deploy Pact Broker (Docker or PactFlow), configure Jenkins stage |
| **DR** | DR Terraform environment (us-east-1), DR runbook, Route 53 failover policy |
| **Security** | WAF rules, SecurityGroups (DB only from EKS CIDR), K8s NetworkPolicies, `REVOKE UPDATE DELETE` on audit table |
| **Cost Control** | Spot instances for dev/staging node groups, RDS stop schedule for dev overnight, ECR cleanup lifecycle |
| **Runbooks** | Rollback, DR failover, DLQ replay, incident response (keep in `infra/runbooks/`) |

---

## 27. Sprint Plan — 16-Week Roadmap

### Phase 1: Foundation (Weeks 1–3)
**DevOps:** Terraform VPC + RDS + ECR + EKS cluster (dev), SQS queues + DLQs, LocalStack docker-compose config, Jenkins EC2 + GitHub webhook, skeleton Jenkinsfile (lint + unit test + push stages)
**Developer:** `common` library — models, schemas, config, logger, circuit breaker, SQS publisher/consumer base, AuditLogWriter, OpenTelemetry init. DB migrations per schema. Docker Compose working locally with LocalStack.

### Phase 2: Core Data Pipeline (Weeks 4–6)
**DevOps:** Full Jenkins pipeline (all stages except canary), Helm charts skeleton deployed to dev namespace. ECR lifecycle policies. Pact Broker deployed.
**Developer:** `data_validator_service` complete (Great Expectations, fallback chain). `screening_service` complete with Pact consumer contract. `scoring_service` complete with Pact provider verification. Unit tests ≥ 70%.

### Phase 3: Trade Logic Services (Weeks 7–9)
**DevOps:** Staging EKS namespace, External Secrets Operator, Prometheus + Grafana (system health dashboard), Jaeger deployed, Alertmanager configured.
**Developer:** `portfolio_service` complete. `risk_service` complete (all week rules, SSE endpoint, SQS event publishing). `batch_service` with RedBeat + idempotent jobs.

### Phase 4: Notifications, Frontend, Audit (Weeks 10–12)
**DevOps:** Production EKS cluster (Multi-AZ), PDB + NetworkPolicy + ResourceQuota for all services. CloudFront + Route 53. Business metrics Grafana dashboard. Canary pipeline.
**Developer:** `notification_service` (SQS consumer, email + SMS). `frontend_service` — all pages including SSE integration (`useRiskStream` hook), AuditTrail page, Calendar (timezone-aware). Audit log writing added to all state-changing operations.

### Phase 5: Hardening & DR (Weeks 13–14)
**DevOps:** DR Terraform (us-east-1), DR runbook tested, RDS point-in-time restore drill. Load test (k6 or Locust) — verify HPA scaling. WAF rules. Cost optimisation (Spot for dev/staging, RDS schedule).
**Developer:** Integration tests (`tests/integration/`). E2E test covering full quarterly cycle. Contract test coverage across all service pairs. Feature flags for all rollout-sensitive logic.

### Phase 6: Production Readiness (Weeks 15–16)
**DevOps + Developer:** Full production deploy with canary. Monitor for 1 week. Fix any issues surfaced by real traffic. Documentation review. Runbook walkthrough (simulate: pod crash, DLQ alert, SL trigger, metric gate failure). Sign off Definition of Done for all services.

---

## 28. Environment Strategy

| Environment | Trigger | K8s Namespace | AWS | SQS | Replicas | Notes |
|---|---|---|---|---|---|---|
| **Local Dev** | `docker compose up` | N/A | LocalStack only | LocalStack SQS | 1 | Full stack, no real AWS |
| **Dev** | Push to `feature/*` | `swingedge-dev` | Shared RDS (dev schema), dev SQS | 1 | Spot nodes |
| **Staging** | Merge to `main` | `swingedge-staging` | Separate RDS (staging), staging SQS | 1–2 | On-Demand nodes |
| **Production** | Git tag `v*` | `swingedge-prod` | Multi-AZ RDS, prod SQS, ElastiCache replica | 2–4 | On-Demand + canary |
| **DR** | Manual failover | `swingedge-dr` | us-east-1 RDS restore, dr SQS | 2 | On-Demand |

---

## 29. Naming Conventions & Standards

| Thing | Convention | Example |
|---|---|---|
| Git branches | `type/description` | `feature/risk-week-rules`, `fix/sl-duplicate-alert` |
| Git commits | Conventional Commits | `feat(risk): add week 7–9 momentum check` |
| Git tags | Semver | `v1.0.0`, `v1.2.3` |
| Docker images | `{service}:{sha}-{env}` | `risk-service:a1b2c3d-prod` |
| K8s resources | kebab-case | `risk-service`, `swingedge-ingress` |
| SQS queues | `swingedge-{event-type}.fifo` | `swingedge-stop-loss-events.fifo` |
| S3 keys | `{bucket}/{category}/{entity}` | `swingedge-market-data/cache/RELIANCE.NS.json` |
| Python files | snake_case | `risk_evaluator.py`, `profit_lock.py` |
| Python classes | PascalCase | `CircuitBreaker`, `AuditLogWriter` |
| React components | PascalCase | `TradeChecklist.tsx`, `RiskStream.tsx` |
| API endpoints | kebab-case, plural nouns, versioned | `/api/v1/portfolio/positions` |
| DB schemas | lowercase | `scoring`, `risk`, `audit` |
| DB tables | snake_case, plural | `risk_evaluations`, `audit_log` |
| DB columns | snake_case | `entry_price`, `occurred_at` |
| Env variables | SCREAMING_SNAKE_CASE | `ALPHA_VANTAGE_API_KEY`, `SQS_STOP_LOSS_QUEUE_URL` |
| Feature flags | kebab-case | `new-ocf-weight-v2`, `enable-macro-auto-exit` |
| SQS event types | SCREAMING_SNAKE_CASE | `STOP_LOSS_HIT`, `PROFIT_LOCK_10PCT` |

---

## 30. Local Development Setup

### Prerequisites

```bash
docker >= 24.0
docker compose >= 2.0
node >= 20          # Frontend
python >= 3.11      # Backend
kubectl             # K8s local inspection
helm >= 3.0         # Helm dry-runs
aws-cli >= 2.0      # AWS interactions
terraform >= 1.5    # Infrastructure
```

### Start Full Stack Locally

```bash
# 1. Clone
git clone https://github.com/your-org/swingEdge.git && cd swingEdge

# 2. Configure environment
cp .env.example .env.dev
# Fill in: ALPHA_VANTAGE_API_KEY, NSE_API_KEY, SMTP credentials
# LocalStack handles SQS, S3, SES, SNS — no real AWS keys needed locally

# 3. Start infrastructure services first (postgres, redis, localstack, jaeger)
docker compose up postgres redis localstack jaeger -d

# 4. Wait for LocalStack to be ready, then create local SQS queues
bash infra/scripts/localstack_setup.sh

# 5. Apply DB migrations (all schemas)
docker compose run --rm scoring python -m alembic upgrade head
docker compose run --rm risk    python -m alembic upgrade head
# ... repeat for each service or use:
bash infra/scripts/migrate_all.sh

# 6. Install common library into each service
pip install -e ./services/common

# 7. Start all services
docker compose up --build

# 8. Seed dev data (optional — creates a sample active cycle)
docker compose run --rm batch python -m app.seeds.dev_cycle

# Services available at:
# Frontend:        http://localhost:3000
# Screening:       http://localhost:8001/docs
# Scoring:         http://localhost:8002/docs
# Portfolio:       http://localhost:8003/docs
# Risk (+ SSE):    http://localhost:8004/docs | http://localhost:8004/api/v1/risk/stream
# Batch:           http://localhost:8005/docs
# Notification:    http://localhost:8006/docs
# Data Validator:  http://localhost:8007/docs
# Jaeger UI:       http://localhost:16686
```

### LocalStack SQS Setup Script

```bash
# infra/scripts/localstack_setup.sh
#!/bin/bash
export AWS_DEFAULT_REGION=ap-south-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export ENDPOINT=http://localhost:4566

QUEUES=(
  "swingedge-stop-loss-events.fifo"
  "swingedge-profit-lock-events.fifo"
  "swingedge-exit-deadline-events.fifo"
  "swingedge-macro-override-events.fifo"
  "swingedge-screening-complete-events.fifo"
  "swingedge-audit-events.fifo"
)

for q in "${QUEUES[@]}"; do
  aws sqs create-queue \
    --queue-name "$q" \
    --attributes '{"FifoQueue":"true","ContentBasedDeduplication":"true"}' \
    --endpoint-url $ENDPOINT
  echo "Created: $q"
done
```

### Run Tests

```bash
# Unit tests (per service)
cd services/scoring_service
pytest tests/unit/ -v --cov=app --cov-fail-under=70

# All unit tests
bash infra/scripts/test_all.sh

# Contract tests (requires Pact Broker running)
pytest tests/contract/ -v

# Integration tests (requires docker compose up)
pytest tests/integration/ -v --env=dev

# Frontend tests
cd services/frontend_service && npm run test
```

---

## 31. Definition of Done

A service is **production-ready** when every item below is checked.

### Developer Checklist (per service)

- [ ] All API endpoints implemented under `/api/v1/`, documented in FastAPI `/docs`
- [ ] `/health` returns 200 (liveness), `/ready` returns 200 only when DB + Redis connected (readiness)
- [ ] `/metrics` endpoint exposing Prometheus metrics (at minimum: request count, latency, error rate)
- [ ] Unit test coverage ≥ 70%
- [ ] Pact consumer contracts written for all downstream API calls
- [ ] Pact provider verification tests written and passing
- [ ] Dockerfile: multi-stage build, non-root user, `HEALTHCHECK` defined
- [ ] All timestamps `TIMESTAMPTZ` in DB, UTC in API responses
- [ ] All external service calls wrapped in `@circuit_breaker`
- [ ] All batch operations idempotent (Redis lock key)
- [ ] Audit log written on every state-changing operation
- [ ] Feature flags used for any logic that may need to be toggled live
- [ ] Graceful shutdown in `lifespan` context manager
- [ ] No hardcoded secrets — all from `os.environ`, documented in `.env.example`
- [ ] `trace_id` propagated in all outgoing HTTP requests (`traceparent` header)
- [ ] Code reviewed via PR, no unresolved comments

### DevOps Checklist (per service deployment)

- [ ] Helm chart: Deployment + Service + HPA + PDB + NetworkPolicy
- [ ] ResourceQuota applied to namespace
- [ ] ExternalSecret syncing correct secrets from AWS Secrets Manager
- [ ] Rolling update strategy: `maxUnavailable: 0`, `maxSurge: 1`
- [ ] `terminationGracePeriodSeconds: 60`, `preStop` sleep hook configured
- [ ] Prometheus scrape annotations on pod template
- [ ] Jenkins pipeline passes all stages (including Trivy + Pact)
- [ ] Canary deploy tested on staging (10% → metric gate → 100%)
- [ ] CloudWatch log group created with correct retention policy
- [ ] Grafana dashboard panel added for this service
- [ ] Alerting rule configured for error rate + pod restarts

---

## Production Readiness Summary

| Category | Status | Key Measure |
|---|---|---|
| Service isolation | DB per schema, IRSA per service | No shared credentials |
| Resilience | Circuit breakers + retries on all external calls | No cascade failures |
| Event-driven | SQS for all async events + DLQs | < 2s SL alert delivery |
| Real-time | SSE stream from risk-service | Dashboard updates < 1s |
| Scheduling | RedBeat (HA) + idempotent jobs | Zero missed jobs on pod restart |
| Observability | Metrics + Traces + Logs (three pillars) | Full trace per trade cycle |
| Deployments | Canary (10% → gate → 100%) + auto-rollback | Zero-downtime releases |
| Compliance | Immutable audit log + SEBI data retention | 5-year audit trail |
| Recovery | RTO < 1hr, RPO < 15min | DR runbook tested quarterly |
| Security | NetworkPolicies + WAF + mTLS-ready + non-root pods | Zero lateral movement |

---

*SwingEdge — Built on rules, not emotions. Engineered for production, not prototypes.*
