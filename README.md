# Trading DevOps Platform

A production-grade, cloud-native algorithmic stock-screening and portfolio-management platform built as a microservices system on AWS EKS. The platform ingests financial metrics, scores stocks against a 100-point fundamental model, evaluates portfolio risk, allocates positions, and dispatches real-time alerts — all observed through a full Prometheus + Grafana monitoring stack.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack](#2-technology-stack)
3. [Service Catalogue](#3-service-catalogue)
4. [Scoring Model](#4-scoring-model)
5. [Infrastructure — AWS + Terraform](#5-infrastructure--aws--terraform)
6. [Kubernetes Manifests](#6-kubernetes-manifests)
7. [Observability — Prometheus & Grafana](#7-observability--prometheus--grafana)
8. [API Reference](#8-api-reference)
9. [Configuration & Environment Variables](#9-configuration--environment-variables)
10. [Local Development](#10-local-development)
11. [Deploying to EKS](#11-deploying-to-eks)
12. [Repository Structure](#12-repository-structure)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        User / Browser                                │
└──────────────────────────┬───────────────────────────────────────────┘
                           │  HTTP (port 80)
                           ▼
              ┌────────────────────────┐
              │   AWS Load Balancer    │  (ELB — frontend-service)
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   frontend-service     │  React SPA  +  Python proxy
              │        :8080           │  /v1/* → scoring-service
              └────────────┬───────────┘
                           │  Internal K8s DNS
         ┌─────────────────┼─────────────────────┐
         │                 │                     │
         ▼                 ▼                     ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│scoring-service│  │ portfolio-service │  │  risk-service    │
│   :8000       │  │    :8003          │  │    :8004         │
└──────┬────────┘  └──────────────────┘  └────────┬─────────┘
       │                                          │
       │ SQS: screening-events                    │ SQS: risk-events
       ▼                                          ▼
┌──────────────┐                        ┌──────────────────┐
│screening-    │                        │notification-     │
│service :8005 │                        │service :8006     │
└──────────────┘                        └──────────────────┘

┌──────────────────────┐   ┌──────────────────────────────────┐
│  batch-service :8001 │   │  AWS Infrastructure               │
│  (scheduled scoring) │   │  ├─ ECR (Docker image registry)  │
└──────────────────────┘   │  ├─ SQS (3 event queues)         │
                           │  ├─ ElastiCache Redis (caching)  │
                           │  ├─ S3 (scoring artifacts)       │
                           │  └─ EKS 1.32 (2× t3.small nodes) │
                           └──────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  Monitoring namespace                             │
│  ├─ Prometheus :9090  (kubernetes_sd scraping)   │
│  └─ Grafana    :3000  (49-panel dashboard)       │
└──────────────────────────────────────────────────┘
```

**Data flow:**

1. User submits financial metrics for a stock via the React UI.
2. **frontend-service** proxies `/v1/*` API calls to **scoring-service**.
3. **scoring-service** applies the 100-point scoring model → returns pass/fail + score.
4. **batch-service** runs scheduled jobs to score multiple tickers in bulk.
5. **screening-service** filters a candidate list and emits a `screening-events` SQS message.
6. **risk-service** evaluates portfolio heat, profit locks, and macro flags; emits `risk-events`.
7. **portfolio-service** allocates position sizes given a universe of scored stocks.
8. **notification-service** consumes SQS events and dispatches email/SMS alerts.
9. **Prometheus** scrapes `/metrics` from every pod every 15 s.
10. **Grafana** visualises 49 real-time panels covering service health, HTTP traffic, latency, and all business KPIs.

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Container runtime | Docker 29.2 |
| Orchestration | AWS EKS 1.32 |
| Node type | `t3.small` × 2 (auto-scaling 1–4) |
| Image registry | AWS ECR |
| IaC | Terraform ≥ 1.5 (AWS provider ~5.0) |
| Backend language | Python 3.11 |
| HTTP framework | `http.server.ThreadingHTTPServer` (stdlib) |
| Frontend | React 18 (Vite, compiled to static assets) |
| Caching | AWS ElastiCache Redis (`cache.t3.micro`) |
| Messaging | AWS SQS (3 standard queues) |
| Object storage | AWS S3 |
| Metrics library | `prometheus_client` 0.25 |
| Monitoring | Prometheus v2.51 + Grafana 10.4 |
| Alerting | Email / SMS via notification-service |
| CI/CD | Jenkins (Jenkinsfile in `infra/jenkins/`) |
| Secrets / Config | Kubernetes ConfigMap |
| Region | `ap-south-1` (Mumbai) |

---

## 3. Service Catalogue

### 3.1 scoring-service `:8000`

The core of the platform. Accepts raw financial metrics for a single stock ticker, runs the 100-point scoring pipeline, and returns a structured score.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus exposition format |
| GET | `/v1/scoring-model` | Returns the full scoring model JSON (weights, thresholds, bands) |
| POST | `/v1/score` | Score a single ticker using provided metrics |
| POST | `/v1/stocks/register` | Register ticker(s) for tracking |
| POST | `/v1/manual-inputs/save-and-score` | Save metrics payload to disk and score |

**Prometheus metrics emitted**

| Metric | Type | Labels | Description |
|---|---|---|---|
| `service_up` | Gauge | `service` | Always 1 while running |
| `scoring_requests_total` | Counter | `outcome` (pass/fail/error) | Per-outcome scoring count |
| `scoring_score_value` | Histogram | — | Distribution of scores 0–100 |
| `scoring_pipeline_duration_seconds` | Histogram | — | End-to-end latency per ticker |
| `stocks_registered_total` | Counter | — | Cumulative tickers registered |

---

### 3.2 batch-service `:8001`

Runs scheduled multi-ticker scoring jobs. Reads from `stocks.txt`, scores each ticker via the scoring pipeline, and writes results to S3 and local outputs.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus exposition format |
| POST | `/v1/batch-score` | Trigger a batch scoring job immediately |

**Prometheus metrics emitted**

| Metric | Type | Labels | Description |
|---|---|---|---|
| `batch_jobs_total` | Counter | `status` (success/partial/error) | Job completion counts |
| `batch_stocks_processed_total` | Counter | `status` (success/error) | Per-ticker processing counts |
| `batch_job_duration_seconds` | Histogram | — | Wall-clock time per batch job |

---

### 3.3 frontend-service `:8080`

Serves the pre-compiled React SPA and acts as a reverse proxy for all `/v1/*` API calls, forwarding them to `scoring-service:8000` over the internal cluster network. This design means the browser never needs to know the scoring-service address — it always talks to the same origin.

**Key behaviour**

- `GET /` → serves `static/index.html`
- `GET /v1/*` → proxied to `$SCORING_SERVICE_URL` (default: `http://scoring-service:8000`)
- `POST /v1/*` → same proxy
- Default API base URL resolves to `window.location.origin` — no hardcoded `localhost`
- LocalStorage entries containing `localhost` are automatically cleared on load

**Environment variables**

```
SCORING_SERVICE_URL=http://scoring-service:8000
FRONTEND_SERVICE_HOST=0.0.0.0
FRONTEND_SERVICE_PORT=8080
```

---

### 3.4 portfolio-service `:8003`

Allocates capital across a set of scored stocks using configurable position-sizing logic.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus exposition format |
| POST | `/v1/portfolio/allocate` | Compute position sizes for a universe of tickers |

**Prometheus metrics emitted**

| Metric | Type | Labels | Description |
|---|---|---|---|
| `portfolio_allocations_total` | Counter | `status` (success/error) | Allocation request counts |
| `portfolio_positions_allocated_total` | Counter | — | Individual positions allocated |

---

### 3.5 risk-service `:8004`

Evaluates portfolio-level risk across three dimensions: portfolio heat (concentration risk), profit-lock thresholds, and macro-environment flags. Emits risk events to SQS for downstream notification.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus exposition format |
| GET | `/v1/risk/stream` | SSE heartbeat stream |
| POST | `/v1/risk/evaluate` | Full risk evaluation (heat + profit locks + macro) |
| POST | `/v1/risk/week-rule` | Check holding-day week rule for a position |

**Risk outcomes**

| Outcome | Meaning |
|---|---|
| `PASS` | Portfolio within all thresholds |
| `CAUTION` | Profit-lock triggered or macro flag raised |
| `BREACH` | Portfolio heat exceeds concentration limit |

**Prometheus metrics emitted**

| Metric | Type | Labels | Description |
|---|---|---|---|
| `risk_evaluations_total` | Counter | `outcome` (PASS/CAUTION/BREACH) | Evaluation counts by outcome |
| `risk_profit_lock_signals_total` | Counter | — | Profit-lock signals triggered |
| `risk_macro_flags_total` | Counter | — | Macro caution flags raised |

---

### 3.6 screening-service `:8005`

Filters a list of candidate stocks against fundamental criteria and ranks them by sector strength. Publishes `screening.completed` events to SQS.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus exposition format |
| POST | `/v1/screen` | Screen candidates and return pass/fail list |
| POST | `/v1/sectors/rank` | Rank candidates by sector |

**Prometheus metrics emitted**

| Metric | Type | Labels | Description |
|---|---|---|---|
| `screening_requests_total` | Counter | `status` (success/error) | Request counts |
| `screening_candidates_evaluated_total` | Counter | — | Total candidate stocks evaluated |

---

### 3.7 notification-service `:8006`

Dispatches formatted alerts over email and SMS channels. Also runs a background SQS consumer thread that processes `notification-events` automatically.

**Endpoints**

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus exposition format |
| POST | `/v1/notifications/send` | Send a notification directly (email or SMS) |
| POST | `/v1/events/consume` | Consume a normalised event and dispatch notification |

**Request body — `/v1/notifications/send`**

```json
{
  "channel": "email",
  "recipient": "trader@example.com",
  "subject": "BREACH alert — MSFT",
  "body": "Portfolio heat exceeds threshold.",
  "severity": "critical"
}
```

**Prometheus metrics emitted**

| Metric | Type | Labels | Description |
|---|---|---|---|
| `notifications_dispatched_total` | Counter | `channel` (email/sms), `status` | Dispatch counts |
| `sqs_messages_consumed_total` | Counter | `queue` | SQS messages successfully processed |
| `sqs_messages_failed_total` | Counter | `queue` | SQS messages that failed processing |

---

### 3.8 Shared HTTP metrics — all services

Every service inherits `MetricsMixin` from `services/common/metrics.py`. This mixin wraps `handle_one_request` and `send_response` to automatically record timing and status codes with zero per-handler boilerplate.

| Metric | Type | Labels | Description |
|---|---|---|---|
| `http_requests_total` | Counter | `service`, `method`, `endpoint`, `status_code` | Request counts |
| `http_request_duration_seconds` | Histogram | `service`, `method`, `endpoint` | Latency (buckets: 5 ms–10 s) |
| `http_requests_in_flight` | Gauge | `service` | Concurrent requests currently being handled |

```python
# Usage — drop MetricsMixin before your BaseHTTPRequestHandler:
class MyHandler(MetricsMixin, BaseHTTPRequestHandler):
    _service_name = "my-service"
    # All HTTP instrumentation is automatic from here
```

---

## 4. Scoring Model

The scoring model lives at `config/scoring_model.json` and is served live by `GET /v1/scoring-model`. Changes to the file are reflected immediately on the next request — no rebuild required.

### 4.1 Scale and threshold

| Parameter | Value |
|---|---|
| Maximum score | 100 points |
| Pass threshold | ≥ 85 — stock qualifies for portfolio entry |
| Fail | Score < 85, no "bad" metric |
| Rejected | Any single metric = "bad" (0.0) → immediate disqualification |

### 4.2 Band scores

| Band | Score multiplier | Meaning |
|---|---|---|
| `excellent` | 1.00 | Significantly above average |
| `good` | 0.75 | Above average |
| `poor` | 0.40 | Below average but acceptable |
| `bad` | 0.00 | Unacceptable — triggers stock rejection |

### 4.3 Sections and weights

| Section | Weight | Metrics |
|---|---|---|
| **Growth Quality** | 30 pts | EPS growth YoY, Revenue growth YoY, OCF growth YoY, OCF/Net Income |
| **Profitability** | 25 pts | Operating margin, Net profit margin, ROIC, ROE |
| **Financial Health** | 15 pts | Debt/Equity, Current ratio, Interest coverage |
| **Valuation Sanity** | 15 pts | PE ratio (vs. industry), PEG ratio, EV/EBITDA |
| **Momentum Monitoring** | 15 pts | Relative strength, Analyst sentiment, Volume trend |

### 4.4 Evaluation sequence

```
Step 1  Score every metric individually against its band thresholds
Step 2  Check disqualification — if ANY metric = bad (0.0), STOP → REJECTED
Step 3  Compute weighted section scores
Step 4  Sum all section scores → total out of 100
Step 5  total ≥ 85 → PASS  |  total < 85 → FAIL
```

### 4.5 Rejection rules (examples)

| Metric | Bad condition | Rejection reason |
|---|---|---|
| EPS growth YoY | < 0% | Business is shrinking |
| Operating margin | < 10% | Lacks pricing power |
| Debt/Equity | > 2.0 | Leverage is dangerous |
| PEG ratio | > 2.0 | Growth doesn't justify valuation |
| Relative strength | underperformance | Institutional money not participating |

### 4.6 Example output

```json
{
  "ticker": "MSFT",
  "total_score": 91.25,
  "pass_threshold": 85,
  "outcome": "pass",
  "disqualified": false,
  "sections": {
    "growth_quality":    { "score": 27.5, "max": 30 },
    "profitability":     { "score": 22.5, "max": 25 },
    "financial_health":  { "score": 14.0, "max": 15 },
    "valuation_sanity":  { "score": 13.5, "max": 15 },
    "momentum_monitoring":{ "score": 13.75,"max": 15 }
  }
}
```

---

## 5. Infrastructure — AWS + Terraform

All AWS resources are defined in `infra/terraform/`. Remote state is stored in the S3 bucket `trading-devops-tf-state` with key `infra/terraform.tfstate`.

### 5.1 Terraform modules

| Module | AWS resource | Key settings |
|---|---|---|
| `modules/vpc` | VPC + subnets | CIDR `10.0.0.0/16`, 2 public + 2 private subnets across 2 AZs |
| `modules/eks` | EKS 1.32 cluster | 2 worker nodes, `t3.small`, auto-scaling 1–4 |
| `modules/iam` | IAM roles | Cluster role, node role, SQS write/read policy |
| `modules/sqs` | SQS queues | `screening-events`, `risk-events`, `notification-events` |
| `modules/s3` | S3 bucket | Scoring outputs + batch artifacts (random suffix) |
| `modules/elasticache` | Redis `cache.t3.micro` | Score caching, 1 node, private subnet |

ECR repositories are created directly in `main.tf` — one per service, with image scanning enabled on push.

### 5.2 Terraform commands

```bash
cd infra/terraform

# 1. Initialise (download providers, configure S3 backend)
terraform init

# 2. Preview all changes
terraform plan -out=tfplan

# 3. Apply
terraform apply tfplan

# 4. Show outputs needed for ConfigMap
terraform output

# 5. Destroy everything
terraform destroy
```

### 5.3 Key Terraform outputs

```bash
terraform output ecr_repositories   # ECR URL per service
terraform output eks_cluster_name   # EKS cluster name
terraform output eks_cluster_endpoint
terraform output redis_endpoint     # → update configmap.yaml REDIS_HOST
terraform output sqs_queue_urls     # → update configmap.yaml SQS_* keys
terraform output s3_bucket_name     # → update configmap.yaml S3_ARTIFACTS_BUCKET
```

### 5.4 AWS account details

| Item | Value |
|---|---|
| Account ID | `951151047337` |
| Region | `ap-south-1` (Mumbai) |
| ECR base URL | `951151047337.dkr.ecr.ap-south-1.amazonaws.com/trading-devops` |
| EKS Kubernetes version | 1.32 |
| Worker node type | `t3.small` (2 vCPU, 2 GB RAM) |
| Cluster name | `trading-devops-cluster` |

---

## 6. Kubernetes Manifests

All manifests live in `infra/k8s/`.

```
infra/k8s/
├── namespace.yaml          # trading-devops namespace
├── configmap.yaml          # Shared env vars (Redis, SQS, S3, region)
├── apps.yaml               # 7 Deployments + 7 Services
├── ingress.yaml            # Optional ALB Ingress
└── monitoring/
    ├── namespace.yaml      # monitoring namespace
    ├── prometheus.yaml     # Prometheus Deployment + RBAC + ClusterRole
    └── grafana.yaml        # Grafana Deployment + 3 ConfigMaps
```

### 6.1 Namespace setup

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/monitoring/namespace.yaml
```

### 6.2 Shared ConfigMap

Update `infra/k8s/configmap.yaml` with the values from `terraform output`, then:

```bash
kubectl apply -f infra/k8s/configmap.yaml
```

### 6.3 Application deployments

Each Deployment in `apps.yaml` has these critical settings:

```yaml
annotations:
  prometheus.io/scrape: "true"    # Prometheus auto-discovery
  prometheus.io/path: "/metrics"  # Scrape path
  prometheus.io/port: "8000"      # Port (varies per service)

containers:
  - imagePullPolicy: Always       # Always pull latest from ECR
    envFrom:
      - configMapRef:
          name: trading-devops-config   # Injects all shared env vars
```

### 6.4 Service ports

| Service | Container port | K8s Service type |
|---|---|---|
| scoring-service | 8000 | ClusterIP |
| batch-service | 8001 | ClusterIP |
| frontend-service | 8080 | **LoadBalancer** (public) |
| portfolio-service | 8003 | ClusterIP |
| risk-service | 8004 | ClusterIP |
| screening-service | 8005 | ClusterIP |
| notification-service | 8006 | ClusterIP |

Only frontend-service exposes a public LoadBalancer. All other services are reachable only within the cluster via internal DNS (`<service>.<namespace>.svc.cluster.local`).

---

## 7. Observability — Prometheus & Grafana

### 7.1 Prometheus

Prometheus uses Kubernetes pod autodiscovery (`kubernetes_sd_configs`, role=pod) to scrape all pods annotated with `prometheus.io/scrape: "true"`. No manual target configuration is required when deploying new services.

```bash
kubectl apply -f infra/k8s/monitoring/prometheus.yaml
```

| Setting | Value |
|---|---|
| Scrape interval | 15 s |
| Evaluation interval | 15 s |
| Retention | 15 days |
| Storage | emptyDir (data lost on pod restart; add a PVC for persistence) |

Access via port-forward:

```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Open http://localhost:9090/targets to verify all 7 pods are being scraped
```

### 7.2 Grafana

```bash
kubectl apply -f infra/k8s/monitoring/grafana.yaml
kubectl rollout restart deployment grafana -n monitoring   # pick up ConfigMap changes
```

| Setting | Value |
|---|---|
| Image | `grafana/grafana:10.4.0` |
| Default credentials | `admin / admin` |
| Dashboard | Auto-provisioned — opens on login |
| Dashboard UID | `trading-devops-prod-v2` |
| Folder | `Trading DevOps` |

**Live Grafana URL:**
`http://a4cd5196b51ca49929633b10e968a421-26719432.ap-south-1.elb.amazonaws.com`

### 7.3 Dashboard — 49 panels across 9 sections

| Section | Panel count | What it shows |
|---|---|---|
| **Fleet Health** | 9 | Per-service UP/DOWN stat + "X/7 healthy" counter |
| **HTTP Traffic** | 4 | Request rate (req/s), error rate %, in-flight count, cumulative totals |
| **Latency** | 3 | P50, P95, P99 request latency per service |
| **Scoring Analytics** | 4 | Pass/fail/error rate, pass %, pipeline P95 duration, stocks registered |
| **Risk Operations** | 6 | Evaluations by outcome, profit lock rate, macro flag rate, running totals |
| **Batch Processing** | 3 | Batch jobs by status, stocks processed, job duration P95 |
| **Screening & Portfolio** | 4 | Screening requests, portfolio allocations, candidates, positions |
| **Notifications & Messaging** | 3 | Notifications by channel, SQS consumed, SQS failed |
| **System Resources** | 5 | Resident memory, CPU usage, open FDs, GC collections, process start times |

### 7.4 Key PromQL queries

```promql
# All 7 services up
sum(service_up) == 7

# HTTP request rate per service (req/s)
sum by (service) (rate(http_requests_total[5m]))

# HTTP 4xx/5xx error rate %
100 * sum by (service) (rate(http_requests_total{status_code=~"[45].."}[5m]))
    / clamp_min(sum by (service) (rate(http_requests_total[5m])), 0.001)

# P95 latency per service
histogram_quantile(0.95,
  sum by (service, le) (rate(http_request_duration_seconds_bucket[5m])))

# Scoring pass rate %
100 * rate(scoring_requests_total{outcome="pass"}[5m])
    / clamp_min(sum(rate(scoring_requests_total[5m])), 0.001)

# Risk BREACH count
risk_evaluations_total{outcome="BREACH"}

# Resident memory per pod
process_resident_memory_bytes

# CPU usage per pod
rate(process_cpu_seconds_total[5m])
```

---

## 8. API Reference

### 8.1 Score a single stock

```bash
curl -X POST http://<frontend-lb>/v1/score \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "MSFT",
    "metrics": {
      "eps_growth_yoy": 22.5,
      "revenue_growth_yoy": 17.0,
      "ocf_growth_yoy": 18.0,
      "ocf_to_net_income": 1.4,
      "operating_margin": 44.0,
      "net_profit_margin": 35.0,
      "roic": 28.0,
      "roe": 40.0,
      "debt_to_equity": 0.3,
      "current_ratio": 2.5,
      "interest_coverage": 25.0,
      "pe_ratio_relative": 0.9,
      "peg_ratio": 1.2,
      "ev_ebitda": 12.0,
      "relative_strength": "strong_outperformance",
      "analyst_sentiment": "more_upgrades",
      "volume_trend": "stable"
    }
  }'
```

**Response**

```json
{
  "ticker": "MSFT",
  "total_score": 91.25,
  "pass_threshold": 85,
  "outcome": "pass",
  "disqualified": false,
  "sections": { "growth_quality": { "score": 27.5 }, "..." : "..." }
}
```

### 8.2 Get the scoring model

```bash
curl http://<frontend-lb>/v1/scoring-model
```

### 8.3 Batch score multiple tickers

```bash
curl -X POST http://<frontend-lb>/v1/batch-score \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["MSFT", "GOOGL", "AAPL"]}'
```

### 8.4 Risk evaluation

```bash
curl -X POST http://<risk-service>:8004/v1/risk/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_value": 1000000,
    "positions": [
      {"ticker": "MSFT", "value": 200000, "unrealised_pnl_pct": 18},
      {"ticker": "GOOGL", "value": 150000, "unrealised_pnl_pct": 5}
    ],
    "profit_lock_threshold_pct": 15.0,
    "macro": { "vix": 22, "market_trend": "neutral" }
  }'
```

**Response**

```json
{
  "status": "CAUTION",
  "portfolio_heat": { "status": "PASS", "concentration_pct": 20 },
  "profit_lock_signals": [
    { "ticker": "MSFT", "unrealised_pnl_pct": 18, "action": "LOCK_50_PCT" }
  ],
  "macro": { "status": "CAUTION", "flags": ["vix_elevated"] },
  "event": { "type": "risk.evaluated", "payload": { "status": "CAUTION" } }
}
```

### 8.5 Portfolio allocation

```bash
curl -X POST http://<portfolio-service>:8003/v1/portfolio/allocate \
  -H "Content-Type: application/json" \
  -d '{
    "total_capital": 500000,
    "candidates": [
      {"ticker": "MSFT", "score": 91},
      {"ticker": "AAPL", "score": 87}
    ],
    "max_positions": 10,
    "max_single_position_pct": 20
  }'
```

### 8.6 Screen candidates

```bash
curl -X POST http://<screening-service>:8005/v1/screen \
  -H "Content-Type: application/json" \
  -d '{
    "candidates": [
      {"ticker": "MSFT", "sector": "Technology", "market_cap": 2800000000000},
      {"ticker": "XYZ",  "sector": "Energy",     "market_cap": 500000000}
    ],
    "min_market_cap": 1000000000,
    "sectors_allowed": ["Technology", "Healthcare"]
  }'
```

### 8.7 Send a notification

```bash
curl -X POST http://<notification-service>:8006/v1/notifications/send \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "recipient": "trader@example.com",
    "subject": "BREACH — Portfolio heat exceeded",
    "body": "Your portfolio has exceeded maximum concentration limits.",
    "severity": "critical"
  }'
```

---

## 9. Configuration & Environment Variables

### 9.1 Kubernetes ConfigMap (`infra/k8s/configmap.yaml`)

Every pod injects all keys via `envFrom: configMapRef: trading-devops-config`.

| Key | Example value | Used by |
|---|---|---|
| `AWS_REGION` | `ap-south-1` | All |
| `REDIS_HOST` | `trading-devops-redis.xxx.cache.amazonaws.com` | scoring, batch |
| `REDIS_PORT` | `6379` | scoring, batch |
| `SQS_SCREENING_EVENTS_URL` | `https://sqs.ap-south-1.amazonaws.com/951151047337/trading-devops-screening-events` | screening |
| `SQS_RISK_EVENTS_URL` | `https://sqs.ap-south-1.amazonaws.com/951151047337/trading-devops-risk-events` | risk |
| `SQS_NOTIFICATION_EVENTS_URL` | `https://sqs.ap-south-1.amazonaws.com/951151047337/trading-devops-notification-events` | notification |
| `S3_ARTIFACTS_BUCKET` | `trading-devops-a3492a6e` | scoring, batch |

### 9.2 Per-service host/port variables

| Service | HOST variable | PORT variable | Default port |
|---|---|---|---|
| scoring-service | `SCORING_SERVICE_HOST` | `SCORING_SERVICE_PORT` | 8000 |
| batch-service | `BATCH_SERVICE_HOST` | `BATCH_SERVICE_PORT` | 8001 |
| frontend-service | `FRONTEND_SERVICE_HOST` | `FRONTEND_SERVICE_PORT` | 8080 |
| portfolio-service | `PORTFOLIO_SERVICE_HOST` | `PORTFOLIO_SERVICE_PORT` | 8003 |
| risk-service | `RISK_SERVICE_HOST` | `RISK_SERVICE_PORT` | 8004 |
| screening-service | `SCREENING_SERVICE_HOST` | `SCREENING_SERVICE_PORT` | 8005 |
| notification-service | `NOTIFICATION_SERVICE_HOST` | `NOTIFICATION_SERVICE_PORT` | 8006 |

All services also accept `SERVICE_HOST` / `SERVICE_PORT` as fallbacks.

---

## 10. Local Development

### 10.1 Prerequisites

- Python 3.11+
- Docker Desktop
- AWS CLI configured (`aws configure`)
- `kubectl` + EKS auth token (`aws eks update-kubeconfig --region ap-south-1 --name trading-devops-cluster`)
- Node.js + pnpm (for frontend dev mode only)

### 10.2 Run a single service locally

```bash
# Install the only runtime dependency
pip install prometheus-client

# All services MUST be run from the project root
# so that `import services.common` resolves correctly
python -m services.scoring_service.server

# Test
curl http://localhost:8000/health
curl http://localhost:8000/metrics
curl http://localhost:8000/v1/scoring-model
```

### 10.3 Docker Compose (all 7 services)

```bash
# Production-like
docker compose up

# Dev mode — live code-reload via volume mounts
docker compose -f docker-compose.dev.yml up
```

### 10.4 Frontend React development

```bash
cd services/frontend_service/webapp
pnpm install
pnpm dev      # Vite dev server at http://localhost:5173

# Build static assets (outputs to services/frontend_service/static/)
pnpm build
```

### 10.5 Rebuild a single service image locally

```bash
# Must run from project root — Dockerfile copies services/ and config/
docker build \
  -f services/scoring_service/Dockerfile \
  -t scoring-service:dev \
  .

docker run -p 8000:8000 scoring-service:dev
```

### 10.6 Running tests

```bash
# (Tests live alongside each service's source code)
python -m pytest services/scoring_service/
python -m pytest services/risk_service/
```

---

## 11. Deploying to EKS

### 11.1 First-time cluster setup

```bash
# Step 1 — provision all AWS infrastructure
cd infra/terraform
terraform init
terraform apply

# Step 2 — configure kubectl
aws eks update-kubeconfig \
  --region ap-south-1 \
  --name trading-devops-cluster

# Step 3 — create namespaces
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/monitoring/namespace.yaml

# Step 4 — update configmap.yaml with terraform output values, then apply
kubectl apply -f infra/k8s/configmap.yaml

# Step 5 — deploy monitoring stack
kubectl apply -f infra/k8s/monitoring/prometheus.yaml
kubectl apply -f infra/k8s/monitoring/grafana.yaml

# Step 6 — deploy application services
kubectl apply -f infra/k8s/apps.yaml

# Step 7 — verify
kubectl get pods -n trading-devops
kubectl get pods -n monitoring
kubectl get svc  -n trading-devops   # find frontend-service EXTERNAL-IP
kubectl get svc  -n monitoring       # find grafana EXTERNAL-IP
```

### 11.2 Build and push all 7 images to ECR

```bash
REGISTRY=951151047337.dkr.ecr.ap-south-1.amazonaws.com
PROJECT=trading-devops

# Authenticate (use explicit --password to avoid Windows pipe issues)
ECR_PWD=$(aws ecr get-login-password --region ap-south-1)
docker login --username AWS --password "$ECR_PWD" $REGISTRY

# Build and push each service from project root
for SERVICE in scoring-service batch-service frontend-service \
               portfolio-service risk-service screening-service \
               notification-service; do
  DIR="${SERVICE//-/_}"
  TAG="$REGISTRY/$PROJECT/$SERVICE:latest"
  docker build -f "services/${DIR}/Dockerfile" -t "$TAG" .
  docker push "$TAG"
  echo "Done: $SERVICE"
done
```

### 11.3 Rolling restart after image push

```bash
# Restart all 7 services
kubectl rollout restart deployment -n trading-devops

# Or restart a single service
kubectl rollout restart deployment/scoring-service -n trading-devops

# Watch progress
kubectl rollout status deployment -n trading-devops
```

### 11.4 Update the Grafana dashboard only

No rebuild needed — the dashboard is provisioned from a ConfigMap:

```bash
# Edit infra/k8s/monitoring/grafana.yaml, then:
kubectl apply -f infra/k8s/monitoring/grafana.yaml
kubectl rollout restart deployment grafana -n monitoring
```

### 11.5 Useful kubectl commands

```bash
# All pods
kubectl get pods -n trading-devops -o wide
kubectl get pods -n monitoring

# Tail service logs
kubectl logs -n trading-devops deployment/scoring-service -f
kubectl logs -n trading-devops deployment/risk-service    -f

# Execute into a pod
kubectl exec -it -n trading-devops deployment/scoring-service -- /bin/sh

# Verify /metrics endpoint from inside the cluster
kubectl exec -n trading-devops deployment/scoring-service -- \
  python -c "
import urllib.request
r = urllib.request.urlopen('http://localhost:8000/metrics')
print(r.read().decode()[:800])
"

# Live query Prometheus
kubectl exec -n monitoring deployment/prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=service_up'

# Check Prometheus scrape targets
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Then open: http://localhost:9090/targets

# Port-forward Grafana locally
kubectl port-forward -n monitoring svc/grafana 3000:80
# Then open: http://localhost:3000 (admin/admin)
```

---

## 12. Repository Structure

```
Trading DevOps Project/
│
├── README.md                          ← This file
├── main.py                            ← CLI entrypoint for local scoring
├── batchrunner.py                     ← CLI entrypoint for batch scoring
├── stocks.txt                         ← Default ticker watchlist
│
├── config/
│   ├── scoring_model.json             ← 100-point scoring model (weights + bands)
│   ├── dev.yaml                       ← Dev environment config
│   ├── staging.yaml
│   └── prod.yaml
│
├── inputs/
│   └── manual_metrics/                ← Sample metric payloads (MSFT.json, MU.json)
│
├── outputs/                           ← Scoring outputs written by scoring-service
│   └── <TICKER>/
│       ├── score.txt
│       ├── standardized_output.json
│       ├── input_payload.json
│       └── audit_log.json
│
├── services/
│   │
│   ├── common/                        ← Shared library imported by all services
│   │   ├── metrics.py                 ← MetricsMixin + all Prometheus metric definitions
│   │   ├── http_utils.py              ← send_json(), read_json()
│   │   ├── logging_utils.py           ← configure_logging()
│   │   ├── configuration.py           ← load_scoring_model(), DEFAULT_OUTPUT_DIR
│   │   └── common/
│   │       ├── messaging/             ← SQS publisher + consumer
│   │       ├── cache/                 ← Redis client
│   │       ├── clients/               ← AlphaVantage, yFinance, NSE API wrappers
│   │       ├── resilience/            ← Circuit breaker + retry decorator
│   │       ├── events/                ← Event types + publisher/consumer
│   │       └── audit/                 ← Audit log writer
│   │
│   ├── scoring_service/
│   │   ├── Dockerfile
│   │   ├── server.py                  ← HTTP server (MetricsMixin)
│   │   ├── pipeline.py                ← ManualScoringPipeline
│   │   ├── engine.py                  ← Core scoring engine
│   │   ├── workflow_store.py          ← Ticker registration + payload persistence
│   │   └── app/logic/                 ← metrics_scorer, checklist_evaluator
│   │
│   ├── batch_service/
│   │   ├── Dockerfile
│   │   ├── server.py                  ← HTTP server (MetricsMixin)
│   │   ├── runner.py                  ← Batch job executor
│   │   └── app/tasks/                 ← screening, pricing, macro, risk_eval, calendar_sync
│   │
│   ├── frontend_service/
│   │   ├── Dockerfile
│   │   ├── server.py                  ← Python HTTP server + /v1/* proxy
│   │   ├── static/                    ← Pre-compiled React SPA
│   │   └── webapp/                    ← React source (Vite + JSX)
│   │
│   ├── portfolio_service/
│   │   ├── Dockerfile
│   │   ├── app/main.py                ← HTTP server (MetricsMixin)
│   │   └── app/logic/allocator.py     ← Position-sizing logic
│   │
│   ├── risk_service/
│   │   ├── Dockerfile
│   │   ├── app/main.py                ← HTTP server (MetricsMixin)
│   │   └── app/logic/                 ← portfolio_heat, profit_lock, macro_monitor, week_rules
│   │
│   ├── screening_service/
│   │   ├── Dockerfile
│   │   ├── app/main.py                ← HTTP server (MetricsMixin)
│   │   └── app/logic/                 ← screener, sector_ranker
│   │
│   └── notification_service/
│       ├── Dockerfile
│       ├── app/main.py                ← HTTP server (MetricsMixin) + SQS consumer thread
│       └── app/channels/              ← email.py, sms.py
│
├── infra/
│   ├── terraform/
│   │   ├── main.tf                    ← Root: ECR, VPC, EKS, IAM, SQS, S3, ElastiCache
│   │   └── modules/
│   │       ├── vpc/                   ← VPC + subnets
│   │       ├── eks/                   ← EKS cluster + managed node group
│   │       ├── iam/                   ← IAM roles + policies
│   │       ├── sqs/                   ← SQS queues
│   │       ├── s3/                    ← S3 bucket
│   │       └── elasticache/           ← Redis cluster
│   │
│   ├── k8s/
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml             ← Shared env vars (Redis, SQS, S3, region)
│   │   ├── apps.yaml                  ← 7 Deployments + 7 Services
│   │   ├── ingress.yaml               ← ALB Ingress (optional)
│   │   └── monitoring/
│   │       ├── namespace.yaml
│   │       ├── prometheus.yaml        ← Prometheus + ClusterRole + RBAC
│   │       └── grafana.yaml           ← Grafana + datasource + dashboard ConfigMaps
│   │
│   └── jenkins/
│       └── Jenkinsfile                ← CI/CD: build → test → push → deploy
│
├── docker-compose.yml                 ← Production-like local stack
├── docker-compose.dev.yml             ← Dev mode with volume mounts
└── .dockerignore
```

---

## 13. Troubleshooting

### Service shows DOWN in Grafana

```bash
# 1. Check pod is Running
kubectl get pods -n trading-devops

# 2. Check the /metrics endpoint responds
kubectl exec -n trading-devops deployment/<service> -- \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:<port>/metrics').read().decode()[:300])"

# 3. Check Prometheus has found the pod as a target
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# http://localhost:9090/targets → look for the pod in "kubernetes-pods"
```

### New image not picked up after ECR push

All deployments use `imagePullPolicy: Always`. Force a rolling restart:

```bash
kubectl rollout restart deployment/<service> -n trading-devops
kubectl rollout status  deployment/<service> -n trading-devops
```

### ECR login returns "400 Bad Request" on Windows (PowerShell)

The PowerShell pipe `|` corrupts the password token. Use the explicit flag instead:

```powershell
$pwd = aws ecr get-login-password --region ap-south-1
docker login --username AWS --password "$pwd" 951151047337.dkr.ecr.ap-south-1.amazonaws.com
```

### Grafana dashboard not loading after ConfigMap update

```bash
kubectl rollout restart deployment grafana -n monitoring

# Verify the dashboard was provisioned
kubectl exec -n monitoring deployment/grafana -- \
  wget -qO- 'http://admin:admin@localhost:3000/api/dashboards/uid/trading-devops-prod-v2' \
  | head -c 200
```

### Browser shows "Unable to load scoring model"

The frontend proxies API calls through itself — the browser must never call scoring-service directly.

1. Confirm `SCORING_SERVICE_URL=http://scoring-service:8000` in the frontend Deployment env.
2. Clear browser localStorage (old `localhost` URLs may be cached from a previous session).
3. Test the proxy: `curl http://<frontend-lb>/v1/scoring-model` — should return JSON.

### Prometheus not scraping a pod

Verify the pod has the required annotations:

```bash
kubectl describe pod <pod-name> -n trading-devops | grep prometheus
```

Expected output:

```
prometheus.io/path: /metrics
prometheus.io/port: 8000
prometheus.io/scrape: true
```

If missing, check the Deployment annotations in `infra/k8s/apps.yaml` are under `spec.template.metadata.annotations` (not `metadata.annotations`).

### Out-of-memory on t3.small nodes

Each t3.small has 2 GB RAM shared across all pods. Monitor with:

```promql
process_resident_memory_bytes
```

Scale the node group if needed:

```hcl
# infra/terraform/main.tf
module "eks" {
  desired_nodes = 3   # increase from 2
  max_nodes     = 5
}
```

Then: `terraform apply`

### Grafana PVC stuck in Pending

The cluster does not have an EBS CSI driver installed. The Grafana Deployment uses `emptyDir` (not a PVC) for storage, so this should not occur with the current manifests. If you ever see this after editing `grafana.yaml`, ensure the storage volume is:

```yaml
volumes:
  - name: storage
    emptyDir: {}    # NOT persistentVolumeClaim
```

---

## Live Endpoints

| Service | URL |
|---|---|
| **Trading Platform (React UI)** | `http://af3526143373744a9977721a904968dd-852303449.ap-south-1.elb.amazonaws.com` |
| **Grafana Monitoring Dashboard** | `http://a4cd5196b51ca49929633b10e968a421-26719432.ap-south-1.elb.amazonaws.com` |

**Grafana login:** `admin / admin`
The production dashboard opens automatically — no navigation needed.




TO RUN : 
# ── 1. Infra ──────────────────────────────────────────────
cd infra/terraform && terraform apply -auto-approve && cd ../..

# ── 2. kubectl ───────────────────────────────────────────
aws eks update-kubeconfig --region ap-south-1 --name trading-devops-cluster

# ── 3. ConfigMap (edit the file first with terraform output values) ──
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/monitoring/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml

# ── 4. ECR login + build + push ──────────────────────────
ECR_PWD=$(aws ecr get-login-password --region ap-south-1)
docker login --username AWS --password "$ECR_PWD" \
  951151047337.dkr.ecr.ap-south-1.amazonaws.com

REGISTRY=951151047337.dkr.ecr.ap-south-1.amazonaws.com/trading-devops
for SERVICE in scoring-service batch-service frontend-service \
               portfolio-service risk-service screening-service \
               notification-service; do
  DIR="${SERVICE//-/_}"
  docker build -f "services/${DIR}/Dockerfile" -t "$REGISTRY/$SERVICE:latest" .
  docker push "$REGISTRY/$SERVICE:latest"
done

# ── 5. Deploy ─────────────────────────────────────────────
kubectl apply -f infra/k8s/monitoring/prometheus.yaml
kubectl apply -f infra/k8s/monitoring/grafana.yaml
kubectl apply -f infra/k8s/apps.yaml

# ── 6. Check ──────────────────────────────────────────────
kubectl get pods -n trading-devops
kubectl get pods -n monitoring
kubectl get svc  -n trading-devops frontend-service
kubectl get svc  -n monitoring     grafana