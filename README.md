# 📈 SwingEdge — Automated Swing Trading Strategy Platform
### Microservice Architecture | DevOps | Docker | Kubernetes | Jenkins | AWS
> **System Version:** 3-Month Cycle, Dynamic Quarterly, India + USA  
> **Team Size:** 2 Engineers | **Stack:** Python · React · PostgreSQL · Redis · AWS EKS · K8 · Docker · Terraform 

---

## 📌 Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture Diagram](#2-system-architecture-diagram)
3. [Microservices Breakdown](#3-microservices-breakdown)
4. [Repository & Folder Structure](#4-repository--folder-structure)
5. [Tech Stack](#5-tech-stack)
6. [DevOps Pipeline — Jenkins CI/CD](#6-devops-pipeline--jenkins-cicd)
7. [Docker Strategy](#7-docker-strategy)
8. [Kubernetes (K8s) on AWS EKS](#8-kubernetes-k8s-on-aws-eks)
9. [AWS Infrastructure Layout](#9-aws-infrastructure-layout)
10. [Database & Storage Architecture](#10-database--storage-architecture)
11. [Team Responsibilities Split](#11-team-responsibilities-split)
12. [Sprint Plan — 12-Week Roadmap](#12-sprint-plan--12-week-roadmap)
13. [Environment Strategy](#13-environment-strategy)
14. [Secrets & Config Management](#14-secrets--config-management)
15. [Monitoring & Observability](#15-monitoring--observability)
16. [Inter-Service Communication](#16-inter-service-communication)
17. [Naming Conventions & Standards](#17-naming-conventions--standards)
18. [Local Development Setup](#18-local-development-setup)

---

## 1. Project Overview

SwingEdge is a **rules-based automated swing trading platform** that operationalizes a disciplined quarterly trading framework for Indian (NSE/BSE) and US (NYSE/NASDAQ) equities.

The system enforces strict, emotion-free trading logic through automated pipelines:

| Pillar | What the System Does |
|---|---|
| **Screening** | Filters universe of stocks by quarterly earnings momentum |
| **Scoring** | Ranks stocks on a multi-dimensional quality matrix |
| **Portfolio Construction** | Allocates capital across top-conviction stocks per quarter |
| **Risk Management** | Enforces stop-losses, profit locks, and macro overrides in real-time |
| **Batch Execution** | Runs quarterly and monthly cycle reviews on schedule |
| **Dashboard** | Surfaces all trade data, checklists, and cycle health in a UI |
| **Notifications** | Sends alerts for stop-loss hits, profit-lock triggers, exit deadlines |

The platform is built as **independent microservices** orchestrated on **AWS EKS (Kubernetes)**, deployed through a **Jenkins CI/CD pipeline**, and fully containerised with **Docker**.

---

## 2. System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                  │
│                                                                        │
│           ┌─────────────────────────────────────┐                     │
│           │         React Frontend (SPA)         │                     │
│           │    Dashboard · Checklists · Reports  │                     │
│           └──────────────┬──────────────────────┘                     │
└──────────────────────────┼─────────────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼─────────────────────────────────────────────┐
│                    AWS LOAD BALANCER (ALB)                              │
│              Route 53 → CloudFront → ALB → Ingress Controller          │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────────┐
│                  KUBERNETES CLUSTER (AWS EKS)                           │
│                                                                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  frontend-  │  │  screening-  │  │   scoring-   │  │ portfolio- │  │
│  │   service   │  │   service    │  │   service    │  │  service   │  │
│  │  (React/    │  │  (FastAPI)   │  │  (FastAPI)   │  │ (FastAPI)  │  │
│  │   Nginx)    │  │              │  │              │  │            │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
│                                                                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │    risk-    │  │    batch-    │  │notification- │  │  api-      │  │
│  │   service   │  │   service    │  │   service    │  │  gateway   │  │
│  │  (FastAPI)  │  │  (Celery +   │  │  (FastAPI +  │  │  (Kong /   │  │
│  │             │  │   Beat)      │  │   SMTP/SNS)  │  │  Traefik)  │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     SHARED INFRASTRUCTURE (common)               │  │
│  │    DB Models · Auth · Validators · Logging · Config Schemas      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────────┐
│                        DATA LAYER (AWS Managed)                         │
│                                                                        │
│    ┌──────────────┐   ┌─────────────┐   ┌──────────────┐              │
│    │  PostgreSQL  │   │    Redis     │   │  S3 Buckets  │              │
│    │  (AWS RDS)   │   │ (ElastiCache)│   │  (Reports,   │              │
│    │              │   │             │   │   Logs, etc) │              │
│    └──────────────┘   └─────────────┘   └──────────────┘              │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL DATA SOURCES                              │
│                                                                        │
│    NSE / BSE API     Yahoo Finance     Alpha Vantage     Screener.in   │
│    (India stocks)   (US stocks)        (Financials)      (Fundamentals)│
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│                      CI/CD LAYER (Jenkins)                              │
│                                                                        │
│    GitHub Push → Jenkins Pipeline → Docker Build → ECR Push            │
│    → Helm Chart Deploy → EKS Rolling Update → Smoke Tests → Notify     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Microservices Breakdown

### 3.1 `frontend-service`
**Owner:** Developer  
**Tech:** React 18, TypeScript, TailwindCSS, Vite, Nginx  
**Port:** 3000

Serves the single-page application. Communicates exclusively through the API Gateway. No direct database access.

**Key Pages/Features:**
- **Dashboard** — Active cycle overview, PnL summary, portfolio heat
- **Stock Screener View** — Results of the 5-Query Research Protocol
- **Trade Tracker** — All open/closed positions with entry, SL, targets
- **Checklist Module** — Pre-entry checklist (all 10 items), interactive tick-off
- **Cycle Review** — Quarterly and monthly review forms with learning log
- **Calendar** — Earnings dates, entry windows, exit deadlines (India + USA)
- **Alerts Panel** — Notification history (SL hits, profit-lock triggers)

---

### 3.2 `screening-service`
**Owner:** Developer  
**Tech:** FastAPI, Python, Pandas, yfinance / NSE API  
**Port:** 8001

Implements the **5-Query Research Protocol — Query 1 & 2**.

**Responsibilities:**
- Fetch stock universe for India (NSE/BSE) and USA (NYSE/NASDAQ)
- Apply quarterly momentum filter: Quarter N > Quarter N−1 (min +5% sequential EPS growth)
- Apply revenue growth filter ≥ 8% YoY
- Apply OCF > Net Income filter (earnings quality)
- Output ranked list of top 25 India + top 25 USA candidates
- Group by sector and identify strongest sectors per market

**Endpoints:**
```
GET  /screen/india          → Ranked India candidates
GET  /screen/usa            → Ranked USA candidates
GET  /screen/sectors/india  → Sector strength breakdown (India)
GET  /screen/sectors/usa    → Sector strength breakdown (USA)
POST /screen/trigger        → Manual or scheduled run trigger
```

---

### 3.3 `scoring-service`
**Owner:** Developer  
**Tech:** FastAPI, Python, Pandas  
**Port:** 8002

Implements the **Metrics Bible (Section 10)** and **Pre-Entry Checklist (Section 5)**. Scores each shortlisted stock 0–100 across all metric categories.

**Scoring Dimensions:**

| Category | Metrics |
|---|---|
| Growth Quality | EPS Growth >10%, Revenue Growth >8%, OCF Growth >10%, OCF/NI >1.0 |
| Profitability | Operating Margin >15%, Net Margin >5%, ROIC >12%, ROE >12% |
| Financial Health | D/E <2.0, Current Ratio >1.5, Interest Coverage >3× |
| Valuation | P/E <Industry+30%, PEG <1.5, EV/EBITDA <15× |
| Momentum | RSI <70, pullback from highs 5–8%, analyst upgrades, volume trend |
| Risk Flags | Counts active exit triggers (margin compression, OCF < NI, etc.) |

**Endpoints:**
```
POST /score/stock            → Score a single stock by ticker
POST /score/batch            → Score a list of tickers
GET  /score/checklist/{id}   → Pre-entry checklist status for a stock
GET  /score/exit-triggers    → Active exit/risk flags for held positions
```

---

### 3.4 `portfolio-service`
**Owner:** Developer  
**Tech:** FastAPI, Python  
**Port:** 8003

Implements **Query 5 of the Research Protocol** — final capital allocation.

**Responsibilities:**
- Accept shortlisted and scored candidates
- Apply capital allocation rules:
  - Min ₹5,000 per position
  - No sector > 60% of total capital
  - India sector ≠ USA sector (correlation control)
  - Stop-loss sizing: position size respects 5–7% SL without breaching risk limits
- Output finalized portfolio construction plan with weights and expected return profile
- Track active portfolios across cycles

**Endpoints:**
```
POST /portfolio/construct    → Build portfolio from scored candidates
GET  /portfolio/active       → Current cycle's active positions
GET  /portfolio/history      → Past cycle portfolios
PUT  /portfolio/position/{id}→ Update position (SL move, partial book)
GET  /portfolio/cycle-score  → Cycle Quality Score (1–5)
```

---

### 3.5 `risk-service`
**Owner:** Developer  
**Tech:** FastAPI, Python, APScheduler  
**Port:** 8004

Enforces **Section 9 (Risk Management Framework)** and **Section 6 (3-Month Holding Cycle)** rules in real-time.

**Responsibilities:**
- Monitor all active positions continuously
- Enforce time-based rules by week:
  - Week 1–2: SL at 5–7% below entry
  - +5% → Move SL to breakeven
  - +8% → Move SL to +3%
  - +10% → Book 40%, SL to +6%
  - +12% → Book additional 30%
  - +15% → Exit or trail weekly
  - Week 13 → Mandatory full exit
- Enforce portfolio heat rules:
  - Month 1: Max −3% drawdown
  - Month 2: Portfolio ≥ previous month close
  - Month 3: Must be in profit or exit
- Detect exit triggers (2+ simultaneously → immediate exit signal)
- Monitor macro risk flags (monthly)

**Endpoints:**
```
GET  /risk/positions/status     → Real-time risk status per position
POST /risk/evaluate/{id}        → Evaluate single position against all rules
GET  /risk/portfolio-heat       → Portfolio-level drawdown status
GET  /risk/exit-signals         → Positions with active exit triggers
GET  /risk/week-rules/{id}      → Which week-specific rule applies today
```

---

### 3.6 `batch-service`
**Owner:** Developer  
**Tech:** Python, Celery, Celery Beat, Redis (broker)  
**Port:** 8005

Runs all **scheduled, time-based jobs** that power the quarterly and monthly automation.

**Scheduled Jobs:**

| Job | Schedule | Description |
|---|---|---|
| `quarterly_screen` | Start of each quarter | Runs full screening pipeline |
| `monthly_review` | 1st of each month | Generates portfolio health report |
| `daily_price_update` | Weekdays 6:30 AM IST / 5 PM EST | Fetches latest OHLC data |
| `risk_evaluation` | Every 30 min (market hours) | Triggers risk-service for all positions |
| `exit_deadline_check` | Daily | Checks Week 13 exit deadlines |
| `earnings_calendar_sync` | Weekly | Syncs upcoming earnings dates |
| `profit_lock_trigger` | Every 1 hr (market hours) | Checks profit-lock thresholds |
| `macro_monitor` | Monthly | Evaluates macro risk flags |

**Endpoints:**
```
POST /batch/run/{job_name}      → Manual trigger of any job
GET  /batch/jobs/status         → Status of all scheduled jobs
GET  /batch/logs/{job_name}     → Last run logs for a job
```

---

### 3.7 `notification-service`
**Owner:** Developer  
**Tech:** FastAPI, Python, AWS SNS, SMTP (SES)  
**Port:** 8006

Sends **real-time alerts** to the trader when rules are triggered.

**Alert Types:**

| Trigger | Channel | Priority |
|---|---|---|
| Stop-loss hit | Email + SMS | CRITICAL |
| Profit-lock threshold reached | Email | HIGH |
| Week 13 exit deadline | Email + SMS | HIGH |
| Earnings approaching (2-week window) | Email | HIGH |
| Macro override triggered | Email + SMS | HIGH |
| Monthly review due | Email | MEDIUM |
| New screened candidates available | Email | LOW |
| Cycle quality score published | Email | LOW |

**Endpoints:**
```
POST /notify/send               → Send manual notification
GET  /notify/history            → Notification log
PUT  /notify/preferences        → Update alert preferences
```

---

### 3.8 `common` (Shared Library)
**Owner:** Developer (with DevOps input on config schemas)  
**Type:** Internal Python package, not a standalone service

**Contains:**
- SQLAlchemy ORM models (Stock, Position, Cycle, Alert, Score, etc.)
- Pydantic schemas for request/response validation
- DB connection factory (PostgreSQL + Redis)
- Authentication utilities (JWT)
- Logging configuration (structured JSON logs → CloudWatch)
- Config loader (reads from environment variables / AWS Secrets Manager)
- Constants (quarter dates, metric thresholds, rule values)
- External API clients (yfinance, NSE, Alpha Vantage wrappers)

---

## 4. Repository & Folder Structure

```
swingEdge/
│
├── services/
│   ├── common/                          # Shared library (installed as package)
│   │   ├── models/                      # SQLAlchemy ORM models
│   │   ├── schemas/                     # Pydantic validation schemas
│   │   ├── db/                          # DB session factory, migrations (Alembic)
│   │   ├── clients/                     # External API clients (NSE, yfinance, Alpha Vantage)
│   │   ├── config.py                    # Central config loader
│   │   ├── logger.py                    # Structured logging setup
│   │   └── constants.py                 # Thresholds, rule values, quarter dates
│   │
│   ├── frontend_service/                # React SPA
│   │   ├── src/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   ├── hooks/
│   │   │   ├── store/                   # Zustand / Redux store
│   │   │   └── api/                     # API client (Axios)
│   │   ├── public/
│   │   ├── Dockerfile
│   │   ├── nginx.conf
│   │   └── package.json
│   │
│   ├── screening_service/
│   │   ├── app/
│   │   │   ├── routers/
│   │   │   ├── logic/                   # Screening + sector ranking logic
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── scoring_service/                 # (Existing in your repo)
│   │   ├── app/
│   │   │   ├── routers/
│   │   │   ├── logic/                   # Metrics bible scoring engine
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── portfolio_service/
│   │   ├── app/
│   │   │   ├── routers/
│   │   │   ├── logic/                   # Allocation engine
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── risk_service/
│   │   ├── app/
│   │   │   ├── routers/
│   │   │   ├── logic/                   # Week rules, SL enforcement, heat monitor
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── batch_service/                   # (Existing in your repo)
│   │   ├── app/
│   │   │   ├── tasks/                   # Celery task definitions
│   │   │   ├── scheduler.py             # Celery Beat schedule
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── notification_service/
│       ├── app/
│       │   ├── routers/
│       │   ├── channels/                # email.py, sms.py, push.py
│       │   └── main.py
│       ├── tests/
│       ├── Dockerfile
│       └── requirements.txt
│
├── infra/                               # DevOps — owned by DevOps engineer
│   ├── terraform/                       # AWS infra as code
│   │   ├── modules/
│   │   │   ├── eks/
│   │   │   ├── rds/
│   │   │   ├── elasticache/
│   │   │   ├── s3/
│   │   │   ├── vpc/
│   │   │   └── iam/
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   ├── staging/
│   │   │   └── prod/
│   │   └── main.tf
│   │
│   ├── helm/                            # Kubernetes Helm charts
│   │   ├── swingEdge/                   # Umbrella chart
│   │   │   ├── Chart.yaml
│   │   │   ├── values.yaml              # Base values
│   │   │   ├── values-dev.yaml
│   │   │   ├── values-prod.yaml
│   │   │   └── templates/
│   │   │       ├── frontend-deployment.yaml
│   │   │       ├── screening-deployment.yaml
│   │   │       ├── scoring-deployment.yaml
│   │   │       ├── portfolio-deployment.yaml
│   │   │       ├── risk-deployment.yaml
│   │   │       ├── batch-deployment.yaml
│   │   │       ├── notification-deployment.yaml
│   │   │       ├── ingress.yaml
│   │   │       ├── hpa.yaml             # Horizontal Pod Autoscaler
│   │   │       ├── configmaps.yaml
│   │   │       └── secrets.yaml         # References AWS Secrets Manager
│   │
│   ├── jenkins/
│   │   ├── Jenkinsfile                  # Main pipeline definition
│   │   ├── Jenkinsfile.hotfix           # Hotfix pipeline
│   │   └── shared-library/              # Reusable Jenkins Groovy functions
│   │
│   └── monitoring/
│       ├── prometheus/
│       │   └── prometheus.yml
│       ├── grafana/
│       │   └── dashboards/
│       └── alertmanager/
│           └── alertmanager.yml
│
├── config/                              # (Existing in your repo)
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
│
├── inputs/                              # (Existing — stock input files)
├── outputs/                             # (Existing — generated reports)
├── logs/                                # (Existing — local logs)
├── failed/                              # (Existing — failed job records)
├── tests/                               # Integration & E2E tests
├── stocks.txt                           # (Existing — stock watchlist)
├── main.py                              # (Existing — local runner entry point)
├── batchrunner.py                       # (Existing — local batch runner)
├── auto_peers_web.py                    # (Existing)
├── run_all.ps1                          # (Existing — local dev run script)
├── docker-compose.yml                   # Local full-stack development
├── docker-compose.dev.yml               # Dev overrides
├── .dockerignore
├── .gitignore
└── README.md                            # This file
```

---

## 5. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18, TypeScript, TailwindCSS, Vite | SPA dashboard |
| **Backend Services** | Python 3.11, FastAPI, Pydantic v2 | All microservices |
| **Task Queue** | Celery + Celery Beat | Async jobs, scheduling |
| **Message Broker** | Redis (AWS ElastiCache) | Celery broker + cache |
| **Primary Database** | PostgreSQL 15 (AWS RDS) | All persistent data |
| **ORM / Migrations** | SQLAlchemy + Alembic | DB access + schema versioning |
| **API Gateway** | Kong / AWS API Gateway | Routing, rate limiting, auth |
| **Containerisation** | Docker, Docker Compose | Local dev + build artifacts |
| **Orchestration** | Kubernetes (AWS EKS) | Production container management |
| **Helm** | Helm 3 | K8s package management |
| **CI/CD** | Jenkins (on EC2) | Automated build-test-deploy pipeline |
| **Container Registry** | AWS ECR | Docker image storage |
| **Cloud Provider** | AWS | All infrastructure |
| **IaC** | Terraform | AWS infra provisioning |
| **Monitoring** | Prometheus + Grafana + CloudWatch | Metrics and dashboards |
| **Logging** | Structured JSON → AWS CloudWatch | Centralised log aggregation |
| **Alerts** | Alertmanager + AWS SNS + SES | Ops alerts + user notifications |
| **Secrets** | AWS Secrets Manager + K8s Secrets | Credential management |
| **DNS / CDN** | Route 53 + CloudFront | DNS and global edge caching |
| **External Data** | yfinance, NSE API, Alpha Vantage, Screener.in | Market data feeds |

---

## 6. DevOps Pipeline — Jenkins CI/CD

**Owner: DevOps Engineer**

### Pipeline Overview

```
Developer pushes code to GitHub
         │
         ▼
   Jenkins detects push via webhook
         │
    ┌────▼────────────────────────────────────────────────────┐
    │                  JENKINS PIPELINE                        │
    │                                                          │
    │  Stage 1: Checkout                                       │
    │  → git clone, identify changed services                  │
    │                                                          │
    │  Stage 2: Lint + Static Analysis                         │
    │  → flake8 (Python), ESLint (React), black (formatter)    │
    │                                                          │
    │  Stage 3: Unit Tests                                     │
    │  → pytest per service, Jest (frontend)                   │
    │  → Coverage threshold: 70% minimum                       │
    │                                                          │
    │  Stage 4: Docker Build                                   │
    │  → Build image for each changed service                  │
    │  → Tag: {service}:{git-sha}-{branch}                     │
    │                                                          │
    │  Stage 5: Security Scan                                  │
    │  → Trivy scan on each built image                        │
    │  → Block on CRITICAL CVEs                                │
    │                                                          │
    │  Stage 6: Push to AWS ECR                               │
    │  → Push tagged image to ECR repository                   │
    │                                                          │
    │  Stage 7: Deploy to Dev                                  │
    │  → helm upgrade --install (dev namespace)                │
    │  → Smoke test: hit /health endpoint per service          │
    │                                                          │
    │  Stage 8 (main branch only): Deploy to Staging           │
    │  → Integration tests run against staging                 │
    │                                                          │
    │  Stage 9 (tag v*): Deploy to Production                 │
    │  → helm upgrade with --atomic (rollback on failure)      │
    │  → Notify team on Slack/Email                            │
    └──────────────────────────────────────────────────────────┘
```

### Jenkinsfile Structure

```groovy
// infra/jenkins/Jenkinsfile (abbreviated structure)

pipeline {
  agent { label 'docker-agent' }

  environment {
    AWS_REGION     = 'ap-south-1'
    ECR_REGISTRY   = '<account-id>.dkr.ecr.ap-south-1.amazonaws.com'
    APP_NAME       = 'swingEdge'
    GIT_COMMIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
  }

  stages {
    stage('Checkout')         { ... }
    stage('Detect Changes')   { ... }  // Only rebuild changed services
    stage('Lint & Format')    { ... }
    stage('Unit Tests')       { ... }
    stage('Docker Build')     { ... }
    stage('Trivy Scan')       { ... }
    stage('Push to ECR')      { ... }
    stage('Deploy Dev')       { ... }
    stage('Integration Tests'){ ... }
    stage('Deploy Staging')   { when { branch 'main' }; ... }
    stage('Deploy Prod')      { when { tag 'v*' }; ... }
  }

  post {
    success { notify('✅ Pipeline passed') }
    failure { notify('❌ Pipeline failed — check logs') }
  }
}
```

### Branch Strategy

| Branch | Purpose | Auto-Deploy To |
|---|---|---|
| `feature/*` | New features | Dev (on PR merge) |
| `main` | Stable integration | Staging |
| `v*` tags (e.g. `v1.2.0`) | Production releases | Production |
| `hotfix/*` | Emergency fixes | Staging → Prod via fast-track |

---

## 7. Docker Strategy

**Owner: DevOps Engineer**

### Per-Service Dockerfile Pattern (Python services)

```dockerfile
# Multi-stage build for lean production images
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim AS production
WORKDIR /app
COPY --from=builder /install /usr/local
COPY services/common /app/common
COPY services/{service_name}/app /app
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE {PORT}
HEALTHCHECK CMD curl -f http://localhost:{PORT}/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{PORT}"]
```

### Frontend Dockerfile (React + Nginx)

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
HEALTHCHECK CMD curl -f http://localhost:3000/ || exit 1
```

### Docker Compose (Local Development)

```yaml
# docker-compose.yml (abbreviated)
version: '3.9'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: swingedge
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  frontend:
    build: ./services/frontend_service
    ports: ["3000:3000"]
    depends_on: [screening, scoring, portfolio, risk]

  screening:
    build: ./services/screening_service
    ports: ["8001:8001"]
    depends_on: [postgres, redis]
    env_file: .env.dev

  scoring:
    build: ./services/scoring_service
    ports: ["8002:8002"]
    depends_on: [postgres, redis]
    env_file: .env.dev

  portfolio:
    build: ./services/portfolio_service
    ports: ["8003:8003"]
    depends_on: [postgres, redis]
    env_file: .env.dev

  risk:
    build: ./services/risk_service
    ports: ["8004:8004"]
    depends_on: [postgres, redis]
    env_file: .env.dev

  batch:
    build: ./services/batch_service
    depends_on: [postgres, redis]
    env_file: .env.dev

  notification:
    build: ./services/notification_service
    ports: ["8006:8006"]
    depends_on: [postgres, redis]
    env_file: .env.dev

  celery-worker:
    build: ./services/batch_service
    command: celery -A app.tasks worker --loglevel=info
    depends_on: [redis, postgres]
    env_file: .env.dev

  celery-beat:
    build: ./services/batch_service
    command: celery -A app.tasks beat --loglevel=info
    depends_on: [redis]
    env_file: .env.dev

volumes:
  postgres_data:
```

---

## 8. Kubernetes (K8s) on AWS EKS

**Owner: DevOps Engineer**

### Cluster Layout

```
AWS EKS Cluster: swingEdge-prod
│
├── Namespace: swingEdge-prod
│   ├── Deployments (one per service)
│   ├── Services (ClusterIP for internal, LoadBalancer for ingress)
│   ├── HorizontalPodAutoscalers
│   ├── ConfigMaps
│   └── Secrets (synced from AWS Secrets Manager via External Secrets Operator)
│
├── Namespace: swingEdge-dev
│   └── (same structure, dev values)
│
├── Namespace: monitoring
│   ├── Prometheus
│   ├── Grafana
│   └── Alertmanager
│
└── Namespace: ingress-nginx
    └── NGINX Ingress Controller
```

### Deployment Template (per service)

```yaml
# infra/helm/swingEdge/templates/scoring-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: scoring-service
  namespace: {{ .Values.namespace }}
spec:
  replicas: {{ .Values.scoringService.replicas }}
  selector:
    matchLabels:
      app: scoring-service
  template:
    spec:
      containers:
        - name: scoring-service
          image: {{ .Values.ecrRegistry }}/scoring-service:{{ .Values.imageTag }}
          ports:
            - containerPort: 8002
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: swingedge-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: swingedge-secrets
                  key: redis-url
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8002
            initialDelaySeconds: 15
            periodSeconds: 20
          readinessProbe:
            httpGet:
              path: /ready
              port: 8002
            initialDelaySeconds: 10
```

### HorizontalPodAutoscaler

```yaml
# infra/helm/swingEdge/templates/hpa.yaml
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
```

### Ingress Configuration

```yaml
# infra/helm/swingEdge/templates/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: swingEdge-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  rules:
    - host: app.swingedge.io
      http:
        paths:
          - path: /
            backend:
              service:
                name: frontend-service
                port: { number: 3000 }
          - path: /api/screen
            backend:
              service:
                name: screening-service
                port: { number: 8001 }
          - path: /api/score
            backend:
              service:
                name: scoring-service
                port: { number: 8002 }
          - path: /api/portfolio
            backend:
              service:
                name: portfolio-service
                port: { number: 8003 }
          - path: /api/risk
            backend:
              service:
                name: risk-service
                port: { number: 8004 }
          - path: /api/notify
            backend:
              service:
                name: notification-service
                port: { number: 8006 }
```

---

## 9. AWS Infrastructure Layout

**Owner: DevOps Engineer (provisioned via Terraform)**

```
AWS Account
│
├── VPC (10.0.0.0/16)
│   ├── Public Subnets (3 AZs)  → ALB, NAT Gateway
│   └── Private Subnets (3 AZs) → EKS nodes, RDS, ElastiCache
│
├── AWS EKS
│   ├── Managed Node Group: t3.medium × 3 (min) / × 8 (max)
│   ├── Cluster Autoscaler enabled
│   └── AWS Load Balancer Controller
│
├── AWS RDS (PostgreSQL 15)
│   ├── Instance: db.t3.medium
│   ├── Multi-AZ: Yes (prod) / No (dev)
│   ├── Automated Backups: 7-day retention
│   └── Encryption at rest: Yes
│
├── AWS ElastiCache (Redis 7)
│   ├── Node: cache.t3.micro
│   └── Used as: Celery broker + app-level cache
│
├── AWS ECR
│   ├── Repo per service: swingEdge/{service-name}
│   └── Image scan on push: Enabled
│
├── AWS S3
│   ├── swingEdge-reports/      → Quarterly/monthly PDF reports
│   ├── swingEdge-logs/         → Archived logs
│   └── swingEdge-terraform/    → Terraform state backend
│
├── AWS Secrets Manager
│   └── Stores: DB URL, Redis URL, API keys, SMTP credentials
│
├── AWS CloudWatch
│   ├── Log groups per service
│   ├── Metric alarms (CPU, Error rate, Latency)
│   └── Dashboards
│
├── AWS Route 53
│   └── app.swingedge.io → CloudFront → ALB
│
├── AWS CloudFront
│   └── CDN for frontend assets + API edge caching
│
├── AWS SES (Simple Email Service)
│   └── Transactional emails (alerts, reports)
│
├── AWS SNS
│   └── SMS notifications (critical alerts: SL hit, mandatory exits)
│
├── AWS IAM
│   ├── EKS Node Role
│   ├── Jenkins Deploy Role (OIDC)
│   └── Service Accounts (IRSA per service)
│
└── Jenkins EC2
    ├── Instance: t3.medium
    ├── Docker installed
    ├── kubectl + helm installed
    └── AWS CLI configured via IAM Role
```

---

## 10. Database & Storage Architecture

### PostgreSQL Schema (Key Tables)

```
stocks          → Master stock list (ticker, name, market, sector)
cycles          → Quarterly cycle records (start_date, end_date, status)
positions       → Active and historical positions per cycle
scores          → Scoring results per stock per run
screen_results  → Screening output per run
portfolio_plans → Capital allocation plans per cycle
risk_events     → Log of all risk rule evaluations
notifications   → Notification history
macro_flags     → Monthly macro risk assessment records
cycle_reviews   → Quarterly review forms (learning log, QCS)
```

### Redis Key Patterns

```
cache:screen:india:{date}     → Cached screening results (TTL: 6hr)
cache:screen:usa:{date}       → Cached screening results (TTL: 6hr)
cache:score:{ticker}:{date}   → Cached score result (TTL: 1hr)
lock:batch:{job_name}         → Distributed lock for batch jobs
celery:*                      → Celery task broker keys
```

---

## 11. Team Responsibilities Split

### 👨‍💻 Developer — Backend + Frontend

**Services to own:**
- `frontend_service` (React dashboard)
- `screening_service` (5-Query Protocol Q1+Q2)
- `scoring_service` (Metrics Bible + Checklist)
- `portfolio_service` (Capital allocation engine)
- `risk_service` (Week rules, SL enforcement, heat monitor)
- `batch_service` (Celery tasks + scheduler)
- `notification_service` (Email + SMS dispatch)
- `common` (Shared models, schemas, clients)

**Deliverables:**
- REST API for each service with `/health` and `/ready` endpoints
- Unit tests with ≥70% coverage per service
- SQLAlchemy models + Alembic migrations in `common`
- Dockerfile per service (multi-stage, non-root user)
- `.env.example` file per service
- API documentation via FastAPI auto-generated `/docs`
- Frontend pages as outlined in `frontend-service` section

---

### ⚙️ DevOps Engineer (You) — Infrastructure + CI/CD

**Responsibilities:**

| Area | Task |
|---|---|
| **Terraform** | Write modules for VPC, EKS, RDS, ElastiCache, S3, ECR, IAM, Secrets Manager |
| **Jenkins** | Set up Jenkins on EC2, configure GitHub webhook, write `Jenkinsfile` |
| **Docker** | Review Dockerfiles, enforce multi-stage builds, set up ECR lifecycle policies |
| **Kubernetes** | Bootstrap EKS cluster, write Helm charts (umbrella + per-service), configure Ingress, HPA, Cluster Autoscaler |
| **CI/CD Pipeline** | Build full Jenkins pipeline: lint → test → docker build → scan → push → deploy |
| **Secrets** | Set up AWS Secrets Manager, integrate with K8s via External Secrets Operator |
| **Monitoring** | Deploy Prometheus + Grafana on cluster, create dashboards, set CloudWatch alarms |
| **Environments** | Maintain dev / staging / prod environment isolation (namespaces + Terraform workspaces) |
| **DNS + CDN** | Configure Route 53, CloudFront distribution |
| **Cost Control** | Set billing alarms, use Spot instances for non-prod EKS nodes |
| **Security** | Enable ECR image scanning, configure SecurityGroups, RBAC for K8s |
| **Logging** | Fluent Bit DaemonSet → CloudWatch log groups per service |
| **Runbooks** | Document rollback procedures, incident response steps |

---

## 12. Sprint Plan — 12-Week Roadmap

### Phase 1: Foundation (Weeks 1–3)
**DevOps:** Terraform VPC + RDS + ECR + basic EKS cluster, Jenkins EC2 setup, GitHub webhooks, skeleton `Jenkinsfile`  
**Developer:** `common` library (models, schemas, config, logging), DB migrations, Docker Compose local setup

### Phase 2: Core Services (Weeks 4–6)
**DevOps:** Full Jenkins pipeline (build + test + push), Helm charts skeleton, dev namespace on EKS, deploy pipeline working end-to-end for one service  
**Developer:** `screening_service` complete with tests, `scoring_service` complete with tests, `batch_service` Celery setup with daily price update job

### Phase 3: Business Logic (Weeks 7–9)
**DevOps:** Staging environment, integration tests in pipeline, Prometheus + Grafana deployed, CloudWatch alarms, Secrets Manager integration  
**Developer:** `portfolio_service` complete, `risk_service` complete with week-based rules, `notification_service` with email + SMS, `frontend_service` core pages (dashboard, trade tracker, checklist)

### Phase 4: Production Hardening (Weeks 10–12)
**DevOps:** Production EKS cluster (Multi-AZ), HPA configured, CloudFront + Route 53, ECR lifecycle policies, incident runbooks, load testing  
**Developer:** Frontend remaining pages (calendar, cycle review, alerts), end-to-end testing, API documentation, quarterly batch job complete

---

## 13. Environment Strategy

| Environment | Trigger | K8s Namespace | AWS Resources | Replicas |
|---|---|---|---|---|
| **Local Dev** | `docker compose up` | N/A | None (all local) | 1 |
| **Dev** | Push to `feature/*` | `swingEdge-dev` | Shared RDS (dev DB) | 1 |
| **Staging** | Merge to `main` | `swingEdge-staging` | Separate RDS (staging DB) | 1–2 |
| **Production** | Git tag `v*` | `swingEdge-prod` | Multi-AZ RDS, ElastiCache | 2–4 |

---

## 14. Secrets & Config Management

**Owner: DevOps Engineer**

All secrets are stored in **AWS Secrets Manager** and synced to Kubernetes via the **External Secrets Operator**.

```
Secrets in AWS Secrets Manager:
  swingedge/prod/database-url
  swingedge/prod/redis-url
  swingedge/prod/alpha-vantage-key
  swingedge/prod/nse-api-key
  swingedge/prod/smtp-credentials
  swingedge/prod/sns-topic-arn
  swingedge/prod/jwt-secret
```

Non-sensitive config lives in `ConfigMaps` (Helm `values.yaml` per environment).

Local development uses a `.env.dev` file (never committed — listed in `.gitignore`).

---

## 15. Monitoring & Observability

**Owner: DevOps Engineer**

### Metrics (Prometheus + Grafana)

**Service-level metrics exposed at `/metrics`:**
- Request count, latency (P50/P95/P99), error rate per endpoint
- Celery task success/failure count, queue depth
- Active positions count, risk events per hour

**Grafana Dashboards:**
- System Health: CPU, memory, pod restarts per service
- Business Dashboard: Active positions, cycle PnL, risk events
- Batch Jobs: Job success rate, last run time, duration

### Logging (CloudWatch)

All services output structured JSON logs:
```json
{
  "timestamp": "2025-01-15T09:30:00Z",
  "service": "risk-service",
  "level": "WARNING",
  "event": "stop_loss_triggered",
  "ticker": "RELIANCE.NS",
  "position_id": "pos_123",
  "message": "Stop-loss hit at 5.2% below entry"
}
```

### Alerting

| Alert | Condition | Action |
|---|---|---|
| Pod crash loop | Restarts > 3 in 5 min | PagerDuty / Slack |
| API error rate | >5% 5xx in 2 min | Slack |
| RDS CPU | >80% for 5 min | Slack |
| Celery queue backup | Queue depth > 100 | Slack |
| Stop-loss triggered | risk-service event | Email + SMS to trader |
| Jenkins pipeline failure | Any stage fails | Email to team |

---

## 16. Inter-Service Communication

All internal service-to-service calls use **HTTP REST over ClusterIP** (within the K8s cluster).

```
frontend-service  →  api-gateway  →  screening/scoring/portfolio/risk/notification
batch-service     →  screening-service   (trigger new screening run)
batch-service     →  risk-service        (trigger position evaluations)
batch-service     →  notification-service (trigger scheduled alerts)
risk-service      →  notification-service (send critical alerts)
portfolio-service →  notification-service (cycle completion report)
```

**No direct DB access across services.** Each service only accesses its own tables. Cross-service data is passed via API calls.

---

## 17. Naming Conventions & Standards

| Thing | Convention | Example |
|---|---|---|
| Git branches | `type/description` | `feature/risk-week-rules` |
| Git commits | Conventional Commits | `feat(risk): add week 7-9 momentum check` |
| Docker images | `{service}:{sha}-{env}` | `scoring-service:a1b2c3d-prod` |
| K8s resources | kebab-case | `risk-service`, `swingEdge-ingress` |
| Python files | snake_case | `risk_evaluator.py` |
| React components | PascalCase | `TradeChecklist.tsx` |
| API endpoints | kebab-case, plural nouns | `/api/portfolio/positions` |
| DB tables | snake_case, plural | `risk_events`, `screen_results` |
| Env variables | SCREAMING_SNAKE_CASE | `ALPHA_VANTAGE_API_KEY` |
| Git tags | semver | `v1.0.0`, `v1.2.3` |

---

## 18. Local Development Setup

### Prerequisites

```bash
# Required tools
docker >= 24.0
docker compose >= 2.0
node >= 20 (for frontend)
python >= 3.11
kubectl
helm >= 3.0
aws-cli >= 2.0
terraform >= 1.5
```

### Start Full Stack Locally

```bash
# 1. Clone repo
git clone https://github.com/your-org/swingEdge.git
cd swingEdge

# 2. Set up environment
cp .env.example .env.dev
# Fill in your API keys in .env.dev

# 3. Start all services
docker compose up --build

# 4. Apply DB migrations
docker compose exec scoring python -m alembic upgrade head

# 5. Access services
# Frontend:  http://localhost:3000
# Screening: http://localhost:8001/docs
# Scoring:   http://localhost:8002/docs
# Portfolio: http://localhost:8003/docs
# Risk:      http://localhost:8004/docs
# Batch:     http://localhost:8005/docs
# Notify:    http://localhost:8006/docs
```

### Run Tests Locally

```bash
# Backend (per service)
cd services/scoring_service
pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend
cd services/frontend_service
npm run test

# All services via script
./run_all.ps1   # Windows
bash run_all.sh # Linux/Mac
```

---

## ✅ Definition of Done

A service is considered **production-ready** when:

- [ ] All endpoints implemented and returning correct responses
- [ ] Unit test coverage ≥ 70%
- [ ] Dockerfile builds successfully (multi-stage, non-root)
- [ ] `/health` and `/ready` endpoints return 200
- [ ] All secrets loaded from environment variables (no hardcoded values)
- [ ] Structured JSON logging in place
- [ ] Prometheus `/metrics` endpoint exposed
- [ ] Helm chart values configured for dev + prod
- [ ] Jenkins pipeline passes all stages
- [ ] Code reviewed and merged via PR

---

*SwingEdge — Built on rules, not emotions. Compounded with discipline.*
