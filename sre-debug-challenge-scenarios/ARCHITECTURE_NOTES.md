# OpenTelemetry Demo — Architecture & Observability Notes

## System Overview

An e-commerce microservices demo (astronomy-themed shop) built to showcase OpenTelemetry instrumentation across 12+ languages. All services export telemetry via OTLP to a central OTel Collector, which fans out to Jaeger (traces), Prometheus (metrics), and OpenSearch (logs).

---

## Service Inventory

### Core Business Services

| Service | Language | Protocol | Port | Criticality | Description |
|---------|----------|----------|------|-------------|-------------|
| **frontend** | TypeScript (Next.js) | HTTP | 8080 | critical | Web UI, SSR, calls most backend services |
| **frontend-proxy** | Envoy | HTTP | 8080 (external) | critical | Reverse proxy, routes to frontend, Grafana, Jaeger, Locust |
| **checkout** | Go | gRPC | 5050 | critical | Orchestrates order placement — calls cart, currency, payment, shipping, email, product-catalog; publishes to Kafka |
| **payment** | Node.js | gRPC | 50051 | critical | Charges credit cards; uses flagd for paymentFailure flag |
| **cart** | .NET (C#) | gRPC | 7070 | high | Shopping cart CRUD; backed by Valkey (Redis-compatible) |
| **product-catalog** | Go | gRPC | 3550 | high | Product listing/lookup; backed by PostgreSQL (astronomy-db) |
| **currency** | C++ | gRPC | 7001 | high | Currency conversion |
| **shipping** | Rust | HTTP | 50050 | high | Shipping quotes and order shipment; calls quote service |
| **ad** | Java | gRPC | 9555 | medium | Contextual advertisements; uses flagd |
| **email** | Ruby | HTTP | 6060 | medium | Order confirmation emails; uses flagd |
| **recommendation** | Python | gRPC | 9001 | medium | Product recommendations; calls product-catalog, uses flagd |
| **product-reviews** | Python | gRPC | 3551 | medium | Product reviews + AI assistant; calls product-catalog, LLM, uses astronomy-db |
| **quote** | PHP | HTTP | 8090 | low | Shipping cost calculation |
| **accounting** | .NET (C#) | Kafka consumer | — | low | Consumes order events from Kafka; writes to astronomy-db |
| **fraud-detection** | Java (Kotlin) | Kafka consumer | — | low | Consumes order events from Kafka for fraud analysis |

### Infrastructure / Supporting Services

| Service | Port | Purpose |
|---------|------|---------|
| **flagd** | 8013 (gRPC), 8016 (OFREP) | Feature flag evaluation (OpenFeature) |
| **flagd-ui** | 4000 | Web UI for managing feature flags |
| **kafka** | 9092 | Event streaming for checkout → accounting/fraud-detection |
| **valkey-cart** | 6379 | In-memory key-value store for cart data |
| **astronomy-db** (PostgreSQL) | 5432 | Relational DB for product catalog, reviews, accounting |
| **llm** | 8000 | Mock LLM for product review AI assistant |
| **image-provider** | 8081 | Serves product images (nginx-based) |
| **load-generator** | 8089 (Locust UI) | Generates synthetic traffic against frontend-proxy |

### Telemetry Stack

| Component | Port | Role |
|-----------|------|------|
| **otel-collector** | 4317 (gRPC), 4318 (HTTP) | Central telemetry hub — receives OTLP, exports to backends |
| **jaeger** | 16686 (UI), 4317 (gRPC) | Distributed tracing backend + UI |
| **prometheus** | 9090 | Metrics storage; receives via OTLP remote-write |
| **grafana** | 3000 | Dashboards and visualization |
| **opensearch** | 9200 | Log storage and search |

---

## Service Dependency Graph

```
                        load-generator
                              │
                        frontend-proxy (Envoy)
                              │
                           frontend
                 ┌────┬───┬──┴──┬────┬────┬────┐
                 │    │   │     │    │    │    │
                ad  cart checkout currency shipping recommendation product-reviews
                │    │    │       │       │         │                │
              flagd valkey │    (none)  quote    product-catalog   product-catalog
                     │    │              │         │    │            │    │
                   flagd  ├─cart         │       flagd  │          llm  astronomy-db
                          ├─currency     │         astronomy-db
                          ├─payment      │
                          ├─shipping     │
                          ├─product-catalog
                          ├─email
                          └─kafka
                              │
                    ┌─────────┴─────────┐
                 accounting      fraud-detection
                    │
                astronomy-db
```

---

## Telemetry Data Flow

```
All Services ──OTLP──► OTel Collector
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
            Jaeger     Prometheus   OpenSearch
           (traces)    (metrics)     (logs)
                ▲           ▲           ▲
                └───────────┼───────────┘
                            │
                         Grafana
```

### OTel Collector Pipeline Details

**Receivers:**
- `otlp` (gRPC :4317, HTTP :4318) — all application telemetry
- `httpcheck/frontend-proxy` — synthetic health check on frontend-proxy
- `nginx` — image-provider nginx status metrics
- `docker_stats` — container-level resource metrics
- `kafkametrics` — Kafka broker/topic/consumer metrics
- `postgresql` — PostgreSQL server metrics (blks, tuples, deadlocks)
- `redis` — Valkey metrics
- `hostmetrics` — CPU, memory, disk, network, processes

**Processors:**
- `memory_limiter` — prevents OOM (80% limit, 25% spike)
- `resourcedetection` — env, docker, system resource attributes
- `transform/sanitize_spans` — normalizes high-cardinality span names (Next.js workaround)

**Connectors:**
- `spanmetrics` — generates `traces_span_metrics_*` metrics from trace spans

**Exporters:**
- Traces → `otlp_grpc/jaeger` (Jaeger :4317)
- Metrics → `otlp_http/prometheus` (Prometheus OTLP endpoint :9090)
- Logs → `opensearch` (index: `otel-logs-YYYY-MM-DD`)

---

## Metrics by Service

### Golden Signal Metrics (Latency & Error Rate)

| Service | Key Metrics | Notes |
|---------|-------------|-------|
| **frontend** | `http_server_duration_milliseconds`, `http_client_duration_milliseconds`, `app_frontend_requests_total` | Legacy OTel HTTP conventions (ms suffix, `http_status_code`) |
| **checkout** | `rpc_server_call_duration_seconds`, `rpc_client_call_duration_seconds`, `http_client_request_duration_seconds` | Modern OTel gRPC + HTTP conventions |
| **cart** | `http_server_request_duration_seconds`, `http_server_active_requests` | Modern OTel HTTP conventions (despite being gRPC — .NET/Kestrel) |
| **shipping** | `http_server_duration_seconds`, `http_server_active_requests` | Rust HTTP server metrics |
| **product-catalog** | `rpc_server_call_duration_seconds`, `db_client_operation_duration_seconds` | gRPC server + PostgreSQL client metrics |
| **currency** | (span metrics only) | C++ — very sparse instrumentation |
| **quote** | (span metrics only) | PHP — only span metrics + custom counter |
| **payment** | `http_client_duration_milliseconds` | Legacy OTel HTTP conventions; mostly internal SDK calls |
| **recommendation** | (span metrics only) | Python — span metrics + system/runtime metrics |
| **product-reviews** | (span metrics only) | Python — span metrics + full system/runtime metrics |

All services also get **span-derived metrics** via the spanmetrics connector:
- `traces_span_metrics_duration_milliseconds` (histogram)
- `traces_span_metrics_calls_total` (counter)

### Custom / Business Metrics

| Metric | Service | Description |
|--------|---------|-------------|
| `app_frontend_requests_total` | frontend | Request count by method/status/target |
| `app_cart_add_item_latency_seconds` | cart | Valkey round-trip for add operations |
| `app_cart_get_cart_latency_seconds` | cart | Valkey round-trip for get operations |
| `app_shipping_items_count_total` | shipping | Total items shipped |
| `app_currency_counter_total` | currency | Conversions by currency code |
| `app_payment_transactions_total` | payment | Transactions by currency |
| `app_recommendations_counter_total` | recommendation | Recommendations served |
| `quotes_total` | quote | Quotes generated by item count |
| `feature_flag_evaluation_*` | cart | Flag evaluation metrics (cartFailure, failedReadinessProbe) |

### Runtime Metrics by Language

| Language | Services | Key Runtime Metrics |
|----------|----------|---------------------|
| **Node.js** | frontend, payment | `nodejs_eventloop_*`, `v8js_gc_*`, `v8js_memory_*` |
| **.NET** | cart, accounting | `dotnet_gc_*`, `dotnet_process_*`, `kestrel_*`, `aspnetcore_*` |
| **Go** | checkout, product-catalog | `go_goroutine`, `go_memory_*`, `go_processor_limit` |
| **Python** | recommendation, product-reviews | `cpython_gc_*`, `process_runtime_cpython_*`, `system_*` |
| **Java** | ad, fraud-detection | (via OTel Java agent — JVM metrics) |
| **Rust** | shipping | (minimal — target_info only) |
| **C++** | currency | (minimal — target_info only) |
| **PHP** | quote | `otel_trace_span_processor_*`, `otel_logs_log_processor_*` |

---

## Logs

All logs flow through: Services → OTLP → OTel Collector → OpenSearch (`otel-logs-*` index)

| Service | Logs? | Severity Field | Key Attributes |
|---------|-------|----------------|----------------|
| **frontend** | Yes (via Envoy access logs) | None (parse from body) | `url.path`, `url.full`, `upstream.cluster` |
| **checkout** | Yes | `severity.text` | `user_id`, `user_currency` |
| **cart** | Yes | `severity.text` | `userId`, `productId`, `quantity` |
| **shipping** | Yes | `severity.text` | `quote.cents`, `quote.dollars`, `quote_service_addr` |
| **product-catalog** | Yes | `severity.text` | `app.product.name`, `app.product.id` |
| **recommendation** | Yes | `severity.text` | `otelTraceID`, `code.file.path`, `code.function.name` |
| **currency** | Yes | `severity.text` | (none) |
| **quote** | Yes | `severity.text` | `context.total` |
| **payment** | Yes | `severity.text` | `transactionId`, `cardType`, `lastFourDigits`, `amount` |
| **product-reviews** | No | — | — |
| **ad** | Not in service_map | — | — |
| **accounting** | Not in service_map | — | — |
| **fraud-detection** | Not in service_map | — | — |

All logs with severity support use: `ERROR/error/Error`, `WARN/warn/Warning`, `INFO/info/Information`
All logs carry `traceId` and `spanId` for trace correlation.

---

## Traces

All traces flow: Services → OTLP → OTel Collector → Jaeger

### Key Server Operations by Service

| Service | Jaeger Name | Server Operations |
|---------|-------------|-------------------|
| **frontend** | frontend | `GET /`, `GET /api/cart`, `POST /api/cart`, `POST /api/checkout`, etc. |
| **checkout** | checkout | `oteldemo.CheckoutService/PlaceOrder` |
| **cart** | cart | `POST /oteldemo.CartService/{AddItem,EmptyCart,GetCart}` |
| **shipping** | shipping | `POST /get-quote`, `POST /ship-order` |
| **product-catalog** | product-catalog | `oteldemo.ProductCatalogService/{GetProduct,ListProducts}` |
| **currency** | currency | `oteldemo.CurrencyService/Convert` |
| **payment** | payment | `oteldemo.PaymentService/Charge`, `charge` |
| **recommendation** | recommendation | `oteldemo.RecommendationService/ListRecommendations` |
| **product-reviews** | product-reviews | `ProductReviewService/{GetProductReviews,GetAverageProductReviewScore,AskProductAIAssistant}` |
| **quote** | quote | `POST /getquote`, `calculate-quote` |

### Critical Trace Path (Checkout Flow)

```
frontend (POST /api/checkout)
  └─► checkout (PlaceOrder)
        ├─► cart (GetCart)
        │     └─► valkey-cart
        ├─► product-catalog (GetProduct) × N items
        │     └─► astronomy-db
        ├─► currency (Convert) × N items
        ├─► shipping (POST /get-quote)
        │     └─► quote (POST /getquote)
        ├─► payment (Charge)
        │     └─► flagd (ResolveFloat — paymentFailure)
        ├─► email (SendOrderConfirmation)
        ├─► cart (EmptyCart)
        │     └─► valkey-cart
        └─► kafka (publish order event)
              ├─► accounting (consume)
              │     └─► astronomy-db
              └─► fraud-detection (consume)
```

---

## Alerting Rules (Prometheus)

| Alert | Expression | Severity | Trigger |
|-------|-----------|----------|---------|
| **SomethingWrongHere** (PaymentServiceUnreachable) | >50% of checkout's downstream RPC calls failing over 5m | critical | Set `paymentUnreachable` flag to "on" |
| ~~HighDatabaseLatency~~ | P95 db_client_operation_duration > 1s for 2m | warning | (commented out) |

---

## Feature Flags (Fault Injection)

All flags managed via flagd, configurable through flagd-ui (:4000).

| Flag | Default | Affects | Description |
|------|---------|---------|-------------|
| `paymentUnreachable` | **on** | checkout → payment | Payment service unavailable (currently active!) |
| `paymentFailure` | off | payment | Fail charge requests at configurable % (0-100%) |
| `cartFailure` | off | cart | Fail cart service |
| `failedReadinessProbe` | off | cart | Readiness probe failure |
| `productCatalogFailure` | off | product-catalog | Fail on specific product |
| `recommendationCacheFailure` | off | recommendation | Cache failure |
| `adManualGc` | off | ad | Trigger full GC |
| `adHighCpu` | off | ad | High CPU load |
| `adFailure` | off | ad | Fail ad service |
| `kafkaQueueProblems` | off | kafka/checkout | Overload Kafka + consumer delay |
| `loadGeneratorFloodHomepage` | off | load-generator | Flood frontend with requests |
| `imageSlowLoad` | off | image-provider | Slow image loading (5s/10s) |
| `emailMemoryLeak` | off | email | Memory leak at configurable multiplier |
| `llmInaccurateResponse` | off | llm | Inaccurate product summary |
| `llmRateLimitError` | off | llm | Intermittent rate limit errors |

**Note:** `paymentUnreachable` is currently set to "on" by default, meaning the PaymentServiceUnreachable alert should be firing.

---

## Infrastructure Services — Observable Via Client Metrics

Some infrastructure services don't emit their own OTel metrics but are observable through client-side instrumentation:

| Infra Service | Observable Through | Client Metrics |
|---------------|-------------------|----------------|
| **valkey-cart** | cart | `app_cart_add_item_latency_seconds`, `app_cart_get_cart_latency_seconds` |
| **astronomy-db** | product-catalog | `db_client_operation_duration_seconds`, `db_sql_connection_*` |
| **flagd** | cart, recommendation, product-reviews, payment, checkout | `feature_flag_evaluation_*`, flagd gRPC client spans |

The OTel Collector also directly scrapes:
- **PostgreSQL** via `postgresql` receiver (blks, tuples, deadlocks)
- **Valkey** via `redis` receiver
- **Kafka** via `kafkametrics` receiver (brokers, topics, consumers)
- **nginx/image-provider** via `nginx` receiver
- **Docker containers** via `docker_stats` receiver
- **Host** via `hostmetrics` receiver (CPU, memory, disk, network)
