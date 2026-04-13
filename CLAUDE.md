# Claude Code Context — OpenTelemetry Demo (RCA Demo Stack)

## Purpose
This repo is a trimmed fork of the OpenTelemetry demo used to build a CNCF-level demo for an **RCA (Root Cause Analysis) agent**. The goal is a live demo where alerts fire, the RCA agent receives them via webhook, and produces correct root cause analysis using traces, metrics, and logs.

## Working File
All work is done against `docker-compose.minimal.yml` — not the original `docker-compose.yml`.

## Active Services
Only these services are in scope:

| Service | Role |
|---|---|
| `frontend` | Entry point, generates HTTP traces |
| `frontend-proxy` | Envoy, routes traffic |
| `load-generator` | Locust, drives synthetic traffic |
| `cart` + `valkey-cart` | Cache layer |
| `checkout` | Critical path, payment calls |
| `product-catalog` + `astronomy-db` | DB traces (PostgreSQL) |
| `recommendation` | Downstream dependency |
| `currency`, `shipping`, `quote` | Supporting services |
| `flagd` | Feature flags for chaos injection |
| `otel-collector` | Telemetry pipeline |
| `jaeger` | Trace storage (:16686) |
| `prometheus` | Metrics + alert evaluation (:9090) |
| `alertmanager` | Alert routing (:9093) |
| `alert-webhook-server` | RCA agent hook-in point (:5001) |
| `grafana` | Dashboards (:3000) |
| `opensearch` | Log storage |

## Commented Out (do not uncomment without discussion)
`ad`, `email`, `payment`, `product-reviews`, `image-provider`, `flagd-ui`, `kafka`, `llm`, `fraud-detection`

## Chaos Injection via flagd
Edit `src/flagd/demo.flagd.json` — flagd hot-reloads, no restart needed.

| Flag | Effect | Alert fired |
|---|---|---|
| `paymentUnreachable` | Checkout payment calls fail (100%) | `HighHTTPErrorRate` on checkout |
| `cartFailure` | Cart returns errors | `HighRPCErrorRate` on cart |
| `productCatalogFailure` | Product catalog errors on one product | `HighRPCErrorRate` on product-catalog |
| `recommendationCacheFailure` | Recommendation cache misses | `HighRPCErrorRate` on recommendation |

Set `"defaultVariant": "on"` to activate, `"off"` to deactivate.

## Alert Pipeline
```
Prometheus (alert-rules.yml, 30s eval)
  → Alertmanager (alertmanager.yml)
    → alert-webhook-server :5001/webhook  ← RCA agent connects here
```

Alert rules: `src/prometheus/alert-rules.yml`
Check firing alerts: `curl http://localhost:5001/alerts/last`

## Key Ports
| Port | Service |
|---|---|
| 80 | frontend-proxy (main entry) |
| 3000 | Grafana |
| 5001 | alert-webhook-server |
| 8089 | Locust load generator UI |
| 9090 | Prometheus |
| 9093 | Alertmanager |
| 16686 | Jaeger |

## Grafana
Accessible directly at `http://localhost:3000` (subpath disabled via env override in compose).

## What NOT to do
- Do not run `docker compose` against `docker-compose.yml` (the full upstream file)
- Do not modify `src/prometheus/alert-rules.yml` without checking existing rules first
- Do not rebuild frontend unless changing frontend source — use the prebuilt image
- Do not add services without discussing impact on memory/resource limits
