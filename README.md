# 📈 SwingEdge — Automated Swing Trading Strategy Platform

> **A rules-based, fully automated swing trading platform** for Indian (NSE/BSE) and US (NYSE/NASDAQ) equities.
> Built as a microservice system deployed on AWS EKS with a Jenkins CI/CD pipeline.

**Stack:** Python 3.11 · stdlib HTTP servers · React · Prometheus · AWS SQS · AWS EKS · AWS ECR · Terraform · Docker · Kubernetes

---

## 📌 Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Architecture Overview](#2-architecture-overview)
3. [Microservices Breakdown](#3-microservices-breakdown)
4. [Folder Structure](#4-folder-structure)
5. [Tech Stack](#5-tech-stack)
6. [Event-Driven Design (SQS)](#6-event-driven-design-sqs)
7. [CI/CD Pipeline — Jenkins](#7-cicd-pipeline--jenkins)
8. [Docker Strategy](#8-docker-strategy)
9. [Kubernetes on AWS EKS](#9-kubernetes-on-aws-eks)
10. [AWS Infrastructure (Terraform)](#10-aws-infrastructure-terraform)
11. [Observability — Metrics & Logs](#11-observability--metrics--logs)
12. [Real-Time Updates — SSE](#12-real-time-updates--sse)
13. [Risk Rules Engine](#13-risk-rules-engine)
14. [Local Development Setup](#14-local-development-setup)

---

## 1. What This Project Does

SwingEdge enforces a **disciplined, emotion-free 3-month swing trading cycle** through automated pipelines. No manual intervention during live cycles.

| Pillar | What It Does |
|---|---|
| **Screening** | Filters universe by quarterly EPS momentum (Q_N > Q_N-1, ≥5% sequential growth) |
| **Scoring** | Ranks each candidate across 14 metrics (growth, profitability, financial health, valuation) |
| **Portfolio Construction** | Allocates capital across top stocks; enforces sector limits and position sizing |
| **Risk Management** | Applies week-specific stop-loss and profit-lock rules |
| **Event Bus** | Async SQS events for SL hits, profit locks, exit deadlines — no polling |
| **Batch Jobs** | Concurrent batch scoring via `ThreadPoolExecutor` |
| **Dashboard** | React UI with SSE event streaming from `risk-service` |
| **Notifications** | Push alerts via AWS SNS (SMS) + SES (email) on every rule trigger |
| **Audit Log** | Structured JSON logs with trace correlation for every trade action |
| **Peer Discovery** | `auto_peers_web.py` fetches peer stocks via `yfinance` + multi-source scoring |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                        │
│            React SPA (Dashboard, Tracker, SSE)          │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTPS / SSE
┌─────────────────────▼───────────────────────────────────┐
│     AWS ALB (internet-facing) → AWS EKS Ingress         │
│           (kubernetes.io/ingress.class: alb)            │
└─────────────────────┬───────────────────────────────────┘
                      │ Path-based routing (/v1/score, /v1/risk, etc.)
┌─────────────────────▼───────────────────────────────────┐
│              AWS EKS (Kubernetes Cluster)                │
│     Namespace: trading-devops | Region: ap-south-1      │
│                                                         │
│  frontend   screening   scoring   portfolio   risk       │
│  (:80)      (:8005)     (:8000)   (:8003)    (:8004)   │
│                                                         │
│  batch             notification                          │
│  (:8001)           (:8006)                              │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │            AWS SQS Event Bus (3 Queues + DLQs)   │   │
│  │  screening-events · risk-events ·                │   │
│  │  notification-events (+ -dlq for each)           │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    DATA LAYER                           │
│  Redis (AWS ElastiCache cache.t3.micro) — score cache   │
│  AWS S3 — scoring outputs, batch artifacts, TF state    │
└─────────────────────────────────────────────────────────┘

EXTERNAL DATA:  yfinance → Screener.in / Alpha Vantage (auto_peers_web.py)

OBSERVABILITY:
  Prometheus → /metrics endpoint (every service)
  Structured JSON logs (every service, written to /app/logs)

CI/CD:
  GitHub → Jenkins → Docker Build (all 7 services)
  → ECR Push → kubectl apply (infra/k8s/) → kubectl set image (rolling update)
```

---

## 3. Microservices Breakdown

### `scoring-service` · Port 8000
- Entry point: `services/scoring_service/server.py` (stdlib `ThreadingHTTPServer`)
- `ManualScoringPipeline` → `ManualScoringEngine` → scores 0–100 across 4 categories:
  - **Growth Quality** (30%) — EPS >10%, Revenue >8%, OCF/NI >1.0
  - **Profitability** (25%) — Operating Margin >15%, ROIC >12%, ROE >12%
  - **Financial Health** (20%) — D/E <2.0, Current Ratio >1.5, Interest Coverage >3×
  - **Valuation Sanity** (15%) — P/E <Industry+30%, PEG <1.5, EV/EBITDA <15×
- Reads from `inputs/`, writes scored JSON to `outputs/`
- Ingress path: `/v1/score`

### `batch-service` · Port 8001
- Runs concurrent scoring jobs via Python `ThreadPoolExecutor` (default: 4 workers, configurable via `BATCH_MAX_WORKERS`)
- Reads stock list from `stocks.txt`; resolves input JSON from `inputs/` directories
- Each job is independent; failures on individual tickers don't block the rest
- Summary output written to `outputs/_batch/summary.json`
- Ingress path: `/v1/batch-score`

### `frontend-service` · Port 8080 (container) / Port 80 (K8s service)
- React SPA served via Nginx
- Connects to `risk-service` via **SSE** for real-time event streaming (`/v1/risk/stream`)
- Pages: Dashboard, Trade Tracker, Checklist, Cycle Review, Calendar, Audit Trail
- Ingress path: `/` (catch-all)

### `portfolio-service` · Port 8003
- Implements capital allocation logic
- Enforces: min ₹5,000/position, no single sector >60%, India sector ≠ USA sector
- Ingress path: `/v1/portfolio`

### `risk-service` · Port 8004
- **Most critical service** — evaluates risk rules during market hours
- Logic modules: `week_rules.py`, `profit_lock.py`, `portfolio_heat.py`, `macro_monitor.py`
- Publishes SQS events (`risk-events` queue) on every trigger via `events/publisher.py`
- Exposes `/v1/risk/stream` SSE endpoint to frontend
- Exposes `/metrics` (Prometheus) and `/health` endpoints
- Ingress path: `/v1/risk`

### `screening-service` · Port 8005
- Implements quarterly momentum filter: Q_N > Q_N-1, min +5% EPS sequential growth
- Produces top 25 India + top 25 USA candidates
- Publishes events to `screening-events` SQS queue on completion
- Ingress path: `/v1/screen`

### `notification-service` · Port 8006
- Consumes from SQS queues
- Routes alerts to AWS SES (email) or SNS (SMS) based on event type and severity
- Critical alerts (SL hit, mandatory exit) trigger both SMS + email
- Ingress path: `/v1/notifications`

### `common` (shared library)
- Shared Python package imported by all services via `services/common/`
- Contains: structured logging (`logging_utils`), Prometheus metrics (`metrics.py`), HTTP utilities (`http_utils`), configuration loader (`configuration.py`), SSE formatter (`sse.py`)

### `auto_peers_web.py` (standalone utility)
- Fetches peer stocks using `yfinance` with multi-source fallback
- Sector mapping via `SECTOR_KEY_MAP`; source-weighted peer scoring
- Used for peer group analysis and input data enrichment

---

## 4. Folder Structure

```
DevOps_Project_Trading_System/
│
├── services/
│   ├── common/              # Shared library — logging, metrics, http_utils, config, sse
│   ├── scoring_service/     # Stock scorer (ManualScoringPipeline, ManualScoringEngine)
│   ├── batch_service/       # ThreadPoolExecutor-based batch scoring runner
│   ├── frontend_service/    # React SPA + Nginx
│   ├── portfolio_service/   # Capital allocation logic
│   ├── risk_service/        # Risk rule engine + SSE stream
│   │   └── app/
│   │       ├── logic/       # week_rules, profit_lock, portfolio_heat, macro_monitor
│   │       ├── events/      # publisher.py (SQS event builder)
│   │       └── sse/         # stream.py (SSE formatter)
│   ├── screening_service/   # Quarterly stock screener
│   └── notification_service/# SQS consumer → SNS/SES alerts
│
├── infra/
│   ├── terraform/           # AWS infra as code
│   │   ├── main.tf          # Root: VPC, EKS, ECR, SQS, S3, ElastiCache, IAM
│   │   └── modules/         # vpc, eks, iam, sqs, s3, elasticache
│   ├── k8s/                 # Kubernetes manifests
│   │   ├── namespace.yaml   # trading-devops namespace
│   │   ├── configmap.yaml   # AWS endpoints (Redis, SQS URLs, S3 bucket)
│   │   └── ingress.yaml     # AWS ALB Ingress (path-based routing, all 7 services)
│   ├── jenkins/             # Jenkinsfile (build → push → deploy)
│   └── monitoring/          # Prometheus / Grafana config
│
├── config/                  # Environment configs
├── inputs/                  # Stock JSON input files
├── outputs/                 # Scored output files (e.g. outputs/MSFT/)
│
├── main.py                  # CLI entry point for manual scoring
├── batchrunner.py           # Local batch job runner
├── auto_peers_web.py        # Peer stock fetcher (yfinance + multi-source)
├── stocks.txt               # Watchlist of stock tickers
├── docker-compose.yml       # Full local stack (7 services)
└── docker-compose.dev.yml   # Dev-mode (same services, dev image tags + container names)
```

---

## 5. Tech Stack

| Category | Technology | Notes |
|---|---|---|
| **Backend** | Python 3.11 | All services use stdlib `http.server.ThreadingHTTPServer` |
| **Frontend** | React (served via Nginx) | SSE-powered real-time risk events |
| **Concurrency** | Python `ThreadPoolExecutor` | Used in `batch-service` for parallel scoring |
| **Event Bus** | AWS SQS (3 standard queues + 3 DLQs) | `screening-events`, `risk-events`, `notification-events` |
| **Cache** | Redis 7 (AWS ElastiCache `cache.t3.micro`) | Score caching; endpoint injected via ConfigMap |
| **Storage** | AWS S3 | Scoring outputs, batch artifacts, Terraform remote state |
| **Containers** | Docker (single-stage, non-root `appuser` UID 10001) | `python:3.11-slim` base |
| **Orchestration** | Kubernetes (AWS EKS 1.32, `t3.small` nodes) | Namespace, ConfigMap, ALB Ingress; `kubectl apply` via Jenkins |
| **IaC** | Terraform ≥ 1.5.0 | VPC, EKS, ECR (per service), SQS + DLQs, S3, ElastiCache, IAM |
| **CI/CD** | Jenkins | Checkout → Docker Build → ECR Push → K8s Deploy |
| **Container Registry** | AWS ECR | `scan_on_push = true`; one repo per service (7 total) |
| **Monitoring** | Prometheus (`prometheus-client`) | `/metrics` on every service; HTTP + business counters |
| **Logging** | Python `logging` → structured JSON | Written to `/app/logs`; `trace_id` correlation |
| **Notifications** | AWS SNS (SMS) + SES (email) | Triggered by `notification-service` consuming from SQS |
| **Peer Data** | `yfinance` | Used in `auto_peers_web.py` for peer stock discovery |
| **AWS Region** | `ap-south-1` (Mumbai) | Terraform default; also in `configmap.yaml` |

---

## 6. Event-Driven Design (SQS)

**Why SQS?** A slow `notification-service` must never block `risk-service` from evaluating positions. SQS decouples the two.

### Queue Map

| Queue | Producer | Consumer |
|---|---|---|
| `trading-devops-screening-events` | screening-service | scoring-service |
| `trading-devops-risk-events` | risk-service | notification-service |
| `trading-devops-notification-events` | risk-service, batch-service | notification-service |

### Key Design Choices (from `infra/terraform/modules/sqs/main.tf`)
- **Standard queues** with long polling (`receive_wait_time_seconds = 20`) — reduces empty receive API calls
- **Dead Letter Queues (DLQs)** — every queue has a paired DLQ (`-dlq` suffix); messages move to DLQ after 3 failed receive attempts (`maxReceiveCount = 3`)
- **Retention:** 24 hours on main queues; 14 days on DLQs
- **IAM** — EKS node group IAM role has SQS access policy (`SendMessage`, `ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes`) on all queues and DLQs
- Queue URLs are Terraform outputs; injected into all pods via the `trading-devops-config` ConfigMap

---

## 7. CI/CD Pipeline — Jenkins

### Actual Pipeline Stages (from `infra/jenkins/Jenkinsfile`)

```
GitHub push
    │
    ▼
1. Checkout         (scm)
2. Docker Login     (aws ecr get-login-password → ap-south-1 ECR)
3. Build Images     (docker build for all 7 services, tagged :${BUILD_NUMBER})
4. Push Images      (docker push to ECR for all 7 services)
5. Deploy K8s       (kubectl apply -f infra/k8s/)
                    (kubectl -n trading-devops set image deployment/<svc> → rolling update)
```

### Environment
| Variable | Value |
|---|---|
| `AWS_REGION` | `ap-south-1` |
| `APP_NAME` | `trading-devops` |
| `K8S_NAMESPACE` | `trading-devops` |
| `IMAGE_TAG` | `${env.BUILD_NUMBER}` |
| `ECR_REGISTRY` | `${AWS_ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com` |

### Services Built & Deployed
`batch-service`, `frontend-service`, `notification-service`, `portfolio-service`, `risk-service`, `scoring-service`, `screening-service`

---

## 8. Docker Strategy

### Python Service Dockerfile (consistent across all 7 services)
```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY config /app/config
COPY services /app/services
COPY stocks.txt /app/stocks.txt   # (where applicable)

RUN pip install --no-cache-dir prometheus-client \
    && mkdir -p /app/outputs /app/logs /app/failed \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser           # Never run as root

EXPOSE <port>

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:<port>/health')"

CMD ["python", "-m", "services.<service>.app.main"]
```

### Key Decisions
- **`python:3.11-slim`** — minimal base image; no build tools in runtime
- **Non-root user** (`appuser`, UID 10001) — enforced in every Dockerfile
- **`prometheus-client`** — the only pip dependency installed at build time
- **HEALTHCHECK** — Python-based `/health` check on every service
- **Shared volumes** — `config/`, `inputs/`, `outputs/`, `logs/` bind-mounted in docker-compose

### docker-compose Setup
- **`docker-compose.yml`** — all 7 services with production image tags (`:local`)
- **`docker-compose.dev.yml`** — same services, dev image tags (`:dev`) + explicit container names (`tradingdevops-*-dev`)

---

## 9. Kubernetes on AWS EKS

### Cluster Config (from `infra/terraform/modules/eks/main.tf`)
| Setting | Value |
|---|---|
| Cluster name | `trading-devops-eks` |
| Kubernetes version | 1.32 |
| Region | ap-south-1 (Mumbai), 2 AZs |
| Node instance type | `t3.small` |
| Node disk size | 20 GB |
| Node scaling | min 1 / desired 2 / max 4 |
| Node subnet | private (10.0.10.0/24, 10.0.11.0/24) |
| Cluster logs | api, audit, authenticator, controllerManager, scheduler |
| Node rolling update | `max_unavailable = 1` |

### K8s Manifests (`infra/k8s/`)

Applied with `kubectl apply -f infra/k8s/` in Jenkins, then image updated per service with `kubectl set image`.

**`namespace.yaml`**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: trading-devops
```

**`configmap.yaml`** — injects all AWS service endpoints into pods
```yaml
data:
  AWS_REGION: "ap-south-1"
  REDIS_HOST: "<elasticache-endpoint>"
  REDIS_PORT: "6379"
  SQS_SCREENING_EVENTS_URL: "https://sqs.ap-south-1.amazonaws.com/.../trading-devops-screening-events"
  SQS_RISK_EVENTS_URL:      "https://sqs.ap-south-1.amazonaws.com/.../trading-devops-risk-events"
  SQS_NOTIFICATION_EVENTS_URL: "https://sqs.ap-south-1.amazonaws.com/.../trading-devops-notification-events"
  S3_ARTIFACTS_BUCKET: "trading-devops-<suffix>"
```

**`ingress.yaml`** — AWS ALB Ingress, path-based routing
```
Annotations:
  kubernetes.io/ingress.class: alb
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/target-type: ip
  alb.ingress.kubernetes.io/healthcheck-path: /health

Path routing:
  /v1/score         → scoring-service:8000
  /v1/batch-score   → batch-service:8001
  /v1/portfolio     → portfolio-service:8003
  /v1/risk          → risk-service:8004
  /v1/screen        → screening-service:8005
  /v1/notifications → notification-service:8006
  /                 → frontend-service:80
```

### IAM (from `infra/terraform/modules/iam/main.tf`)
| Role | Attached Policy |
|---|---|
| EKS Cluster Role | `AmazonEKSClusterPolicy` |
| EKS Node Group Role | `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly` |
| Node Group (SQS) | Custom policy: `SendMessage`, `ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes` on all SQS queues + DLQs |

---

## 10. AWS Infrastructure (Terraform)

All provisioned via Terraform with per-component modules. Remote state in S3 (`trading-devops-tf-state`, `ap-south-1`).

```
VPC (10.0.0.0/16)
├── Public Subnets  (2 AZs: 10.0.1.0/24, 10.0.2.0/24)    → ALB, NAT Gateway
└── Private Subnets (2 AZs: 10.0.10.0/24, 10.0.11.0/24)  → EKS nodes, ElastiCache

EKS:         k8s 1.32, t3.small nodes (20 GB disk), min 1 / desired 2 / max 4
ECR:         1 repo per service (7 total), scan_on_push = true, MUTABLE tags
SQS:         3 standard queues + 3 DLQs, long polling, 24h / 14d retention
ElastiCache: Redis 7, cache.t3.micro, 1 node, private subnet
S3:          1 bucket (random suffix), scoring outputs + batch artifacts
IAM:         Cluster role, node group role, SQS access policy
Terraform state: s3://trading-devops-tf-state/infra/terraform.tfstate
```

### Terraform Modules
| Module | What It Provisions |
|---|---|
| `vpc` | VPC, public/private subnets, route tables, NAT Gateway |
| `eks` | EKS cluster + managed node group |
| `iam` | Cluster IAM role, node group IAM role, SQS access policy |
| `sqs` | 3 queues + 3 DLQs; outputs queue ARNs and URLs |
| `s3` | Single S3 bucket for outputs and artifacts |
| `elasticache` | Redis single-node cluster (cache.t3.micro) |

---

## 11. Observability — Metrics & Logs

### Metrics (Prometheus)
Every service exposes `/metrics` using `prometheus-client`. Defined in `services/common/metrics.py`:

```python
# Shared across all services (labelled by service name)
SERVICE_UP                     = Gauge("service_up", ...)
HTTP_REQUESTS_TOTAL            = Counter("http_requests_total", ...)
HTTP_REQUEST_DURATION_SECONDS  = Histogram("http_request_duration_seconds",
                                   buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25,
                                            0.5, 1.0, 2.5, 5.0, 10.0])
HTTP_REQUESTS_IN_FLIGHT        = Gauge("http_requests_in_flight", ...)

# Business metrics (risk-service)
RISK_EVALUATIONS_TOTAL         = Counter("risk_evaluations_total", ...)
RISK_MACRO_FLAGS_TOTAL         = Counter("risk_macro_flags_total", ...)
RISK_PROFIT_LOCK_SIGNALS_TOTAL = Counter("risk_profit_lock_signals_total", ...)
```

### Logs
Structured JSON logs from every service via `services/common/logging_utils.py`. Written to `/app/logs`. Format includes `timestamp`, `level`, `service`, `message`, `trace_id`, `module`.

---

## 12. Real-Time Updates — SSE

**Why SSE over WebSocket?** Risk events are one-directional (server → client). SSE is simpler, works over standard HTTP/1.1, and doesn't require a WebSocket upgrade — important for passing through ALB and Nginx.

**How it works:**
1. `risk-service` exposes `GET /v1/risk/stream`
2. Endpoint responds with `Content-Type: text/event-stream`
3. Events are formatted via `services/common/sse.py` (`format_sse`)
4. The React frontend `useSSE` hook connects and renders events in real time
5. Nginx config must have `proxy_buffering off` — without it, Nginx buffers SSE events and they arrive in batches

---

## 13. Risk Rules Engine

The `risk-service` evaluates week-based rules using dedicated logic modules:

| Module | Purpose |
|---|---|
| `app/logic/week_rules.py` | Maps holding days → `rule_for_holding_days()` |
| `app/logic/profit_lock.py` | Evaluates profit-lock thresholds |
| `app/logic/portfolio_heat.py` | Evaluates aggregate portfolio heat |
| `app/logic/macro_monitor.py` | Evaluates macro flag conditions |
| `app/events/publisher.py` | Builds SQS event envelope (`build_risk_event`) |
| `app/sse/stream.py` | Formats SSE events (`format_sse`) |

**Risk rule triggers (Week 1–13 cycle):**
| Gain | Action |
|---|---|
| +5% | Move SL to breakeven |
| +10% | Book 40%, SL to +6% |
| +15% | Exit or trail weekly |
| Week 13 | Mandatory full exit |

---

## 14. Local Development Setup

```bash
# 1. Clone
git clone https://github.com/Manohar0441/DevOps_Project_Trading_System
cd DevOps_Project_Trading_System

# 2. Start all 7 services locally
docker-compose up --build

# Services available at:
#   Frontend:      http://localhost:8080
#   Scoring:       http://localhost:8000
#   Batch:         http://localhost:8001
#   Portfolio:     http://localhost:8003
#   Risk:          http://localhost:8004
#   Screening:     http://localhost:8005
#   Notification:  http://localhost:8006

# 3. Run manual scoring pipeline (CLI)
python main.py MSFT --input-json inputs/MSFT.json --output-dir outputs/

# 4. Run batch scoring (all tickers in stocks.txt)
python batchrunner.py

# 5. Fetch peer stocks for a ticker
python auto_peers_web.py  # uses yfinance
```

### Volume Mounts (docker-compose)
| Host Path | Container Path | Access |
|---|---|---|
| `./config` | `/app/config` | read-only |
| `./inputs` | `/app/inputs` | read-write (scoring), read-only (batch) |
| `./outputs` | `/app/outputs` | read-write |
| `./logs` | `/app/logs` | read-write |
| `./stocks.txt` | `/app/stocks.txt` | read-only (batch/screening) |

---

## Architecture Decision Summary

| Decision | Chosen Approach | Reason |
|---|---|---|
| HTTP servers | Python stdlib `ThreadingHTTPServer` | Zero extra dependencies; ships with Python 3.11 |
| Concurrency | `ThreadPoolExecutor` (batch) | Simple, sufficient for I/O-bound scoring jobs |
| Event bus | AWS SQS (3 queues + DLQs) | Managed service; decouples risk from notification; DLQs catch failures |
| DB/State | Redis (cache) + S3 (outputs) | No relational DB needed for current scope |
| K8s routing | AWS ALB Ingress (path-based) | Single internet-facing ALB routes all 7 services by path prefix |
| Config injection | K8s ConfigMap | SQS URLs, Redis endpoint, S3 bucket injected at deploy time from Terraform outputs |
| IaC | Terraform modules | Reproducible AWS infra; remote state in S3 |
| CI/CD | Jenkins (5-stage pipeline) | Build → push → deploy; straightforward and self-contained |
| Rolling updates | `kubectl set image` | Built into Kubernetes; no additional tooling needed |
| Real-time UI | SSE | One-directional; simpler; works through all HTTP proxies including ALB |
| Container security | Non-root `appuser` (UID 10001) | Enforced in every Dockerfile |

---

*Built by Manohar — DevOps + Python microservices project for learning and interview preparation.*
