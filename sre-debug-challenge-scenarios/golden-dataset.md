# Golden Dataset — SRE Debug Challenge Scenarios

This document is the **grading rubric** for the three training scenarios. It defines, for each case:

1. The **exact alert payload** the SRE_Trainee receives (the single pager they get — nothing else).
2. The **canonical RCA** the trainee is expected to produce.
3. The **supporting evidence** they should cite (specific PromQL / OpenSearch / Jaeger queries and what each returns).
4. The **red herrings** they may be tempted by and the specific signal that disproves each.
5. The **grading keywords** a grader (human or RCA agent) looks for in the trainee's write-up.
6. The **out-of-scope conclusions** that, if the trainee reaches them, indicate either cheating (repo access) or a misdiagnosis.

Threat Model **TM-A** applies throughout: the SRE_Trainee has only Prometheus (`:9090`), Alertmanager (`:9093`), Grafana (`:3000`), Jaeger (`:16686`), and OpenSearch (via Grafana OpenSearch datasource). No repo. No shell. No flagd-ui.

---

## Case 1 — `DataAnomalyWarning` (HARD / Deceptive)

### Alert payload as delivered to the trainee

```yaml
alert: DataAnomalyWarning
severity: warning
scenario: case1

summary: |
  Elevated rate of zero-value orders detected in checkout — possible payment or pricing issue

description: |
  Over 15% of orders placed in the last 5 minutes have shipping cost under $1.
  Investigate payment service charge logic and verify checkout arithmetic for cart totals.
  This may indicate a checkout pricing regression, a currency conversion zero-rate,
  or a payment processor discount rule misconfiguration.
```

### Expected first-read reaction

"Zero-value orders — smells like payment, checkout arithmetic, or currency. I'll start with payment."

*This is the intended deception.* The alert was designed to steer the trainee toward three plausible-but-wrong subsystems before they find the real one.

### Canonical RCA narrative (what the trainee should write in their postmortem)

> **Root cause.** The `quote` service (PHP) is silently catching an `InvalidArgumentException('numberOfItems not provided')` inside `calculateQuote()` on approximately 20–40% of inbound `POST /getquote` requests, swallowing the exception into an `exception` event on its internal `calculate-quote` span, and returning `0` as the quote value to the caller. The downstream path — shipping, checkout, payment — all treat `0` as a legitimate amount and process the order end-to-end with no errors. The order ships and the customer is charged $0 for shipping.
>
> **Evidence chain.** I traced a PlaceOrder trace with `app.shipping.amount = 0` down from checkout → shipping → quote → `calculate-quote` (internal span). The `calculate-quote` span's **events panel** contains an `exception` event whose `exception.type=InvalidArgumentException` and `exception.message=numberOfItems not provided`. Every hop below checkout returns HTTP/gRPC OK, which is why no error metric or error log ever fires — the failure is recorded on the span events panel only, not as a status code or log line.
>
> **Scope.** ~15–40% of PlaceOrder traces during the alert window exhibit `app.shipping.amount < 1.00`. The rest are healthy.
>
> **Handoff.** Escalate to the quote service owner with trace IDs. The owner should either (a) fix the upstream caller to always provide `numberOfItems` or (b) change the exception handler in `calculateQuote()` to surface the error as a non-2xx response instead of silently returning 0.

### Required evidence (the trainee must cite all of these)

| # | Tool | Query | What they should see |
|---|------|-------|----------------------|
| E1 | Prometheus | `sum(rate(app_order_shipping_cost_usd_total{service_name="checkout", bucket="zero"}[5m])) / sum(rate(app_order_shipping_cost_usd_total{service_name="checkout"}[5m]))` | Ratio > 0.15 — confirms alert is real, not a false positive |
| E2 | Jaeger | `service=checkout operation=oteldemo.CheckoutService/PlaceOrder` with filter `app.shipping.amount < 1.0`, last 15m | ≥1 matching trace |
| E3 | Jaeger | Open the trace; inspect root PlaceOrder span attributes | `app.shipping.amount=0, app.order.amount=0` (both zero — so arithmetic is `0+0=0`, not a math bug) |
| E4 | Jaeger | Descend checkout → shipping `POST /get-quote` server span | Returns `cost_usd {units:0, nanos:0}`; `SendingQuoteValue dollars=0 cents=0` log on the span |
| E5 | Jaeger | Descend shipping → quote `POST /getquote` server span | HTTP 200, body `0`; `Calculated quote total=0` log on the span |
| E6 | Jaeger | Open `calculate-quote` INTERNAL span (child of quote server span); inspect **events panel** | Event named `exception`, with `exception.type=InvalidArgumentException`, `exception.message` contains `numberOfItems` |
| E7 | OpenSearch | `resource.service.name.keyword:(checkout OR shipping OR quote) AND severity.text:(ERROR OR WARN)` correlated by `traceId` | Zero hits on corrupted traces — confirms silent corruption (no logs on the hot path) |

### Red herrings and their disproof

| Hypothesis | Evidence the trainee finds | Why it's wrong |
|---|---|---|
| **Payment is failing** | PromQL `rate(rpc_client_call_duration_seconds_count{service_name="checkout", rpc_method="oteldemo.PaymentService/Charge", rpc_response_status_code!="OK"}[5m])` returns **0**. Jaeger `service=payment error=true` returns **0 traces**. | Payment processed every corrupted order successfully. Payment is not the cause. |
| **Checkout arithmetic bug** | Root PlaceOrder span shows `app.order.amount=0` AND `app.shipping.amount=0`. The sum of these is 0 — arithmetically correct for the inputs. | The inputs are already bad when they reach checkout's math. Checkout's math is fine. |
| **Currency zero-rate** | Jaeger `oteldemo.CurrencyService/Convert` spans all return `OK` with `STATUS_CODE_OK`. Conversions involve USD → USD, which is a no-op. | Currency service is healthy. Not the cause. |
| **Cart has zero quantities** | In the trace, the `oteldemo.CartService/GetCart` child span response contains `items[*].quantity` all `> 0`. | Cart returns real items with real quantities. Not the cause. |

### Keywords the grader looks for in the trainee's write-up

**Required (must be present — RCA is incorrect without these):**
- `quote` (the service name)
- `calculate-quote` (the span)
- `exception` event OR `span event` (the location of the forensic signal)
- `numberOfItems` (the literal substring in the exception message)
- `silent` / `swallowed` / `caught` / `ignored` (the behavior description)

**Strongly expected (RCA is incomplete without):**
- `20%` / `40%` / percentage of affected traffic (scope quantification)
- `HTTP 200` / `gRPC OK` / `no error status` (understanding why it's silent)
- Reference to walking `checkout → shipping → quote` (trace descent)

**Acceptable but not required:**
- Mention of `InvalidArgumentException` (the Java-style name — trainee may have said "validation exception" which is fine)
- The word `PHP` — if trainee got here via `target_info.telemetry_sdk_language=php` that's a legitimate MLT-only deduction; if they reference reading the source, that's a TM-A violation (see below)

### Out-of-scope conclusions (if the trainee writes these, something is wrong)

- **"I read `src/quote/app/routes.php` and saw the exception handler."** → TM-A violation. Flag for re-training.
- **"I used the flagd-ui to see the `quoteSilentCorruption` flag was on."** → TM-A violation.
- **"The root cause is payment."** → Misdiagnosis. Case 1 was designed to mislead toward this.
- **"The root cause is that checkout computed `0 + 0 = 0` incorrectly."** → Misdiagnosis. Arithmetic is correct; inputs are bad.

### Time-to-solve budget

- **Target: 45–90 minutes.**
- Faster than 15 minutes: red-flag the session — either the trainee had prior knowledge or the scenario leaked.
- Longer than 90 minutes: acceptable during first exposure; coach on trace-descent patterns.

---

## Case 2 — `PaymentServiceUnreachable` (EASY / Prescriptive)

### Alert payload as delivered to the trainee

```yaml
alert: PaymentServiceUnreachable
severity: critical
scenario: case2
rpc_method: "oteldemo.PaymentService/Charge"

summary: |
  oteldemo.PaymentService/Charge UNAVAILABLE from checkout

description: |
  Over 50% of oteldemo.PaymentService/Charge calls from checkout returned gRPC UNAVAILABLE in the last 5 minutes.
  Jaeger search: service=checkout error=true
  OpenSearch query: resource.service.name.keyword:checkout AND severity.text:ERROR
```

### Expected first-read reaction

"Payment is unreachable from checkout. Alert tells me exactly where to look — Jaeger, then OpenSearch. Let's go."

### Canonical RCA narrative

> **Root cause.** The `checkout` service is attempting to reach the payment service at the literal hostname `badAddress:50051` instead of the expected `payment:50051`. DNS resolution fails (or connection refused — either manifests as gRPC `UNAVAILABLE`). Every `oteldemo.PaymentService/Charge` call from checkout is failing; the payment container itself is healthy and idle.
>
> **Evidence chain.** Jaeger `service=checkout error=true` returns many failing traces. Inside any one of them, the `oteldemo.PaymentService/Charge` child span is red and carries `rpc.grpc.status_code=14` (UNAVAILABLE). The span's `server.address` / `peer.address` attribute shows `badAddress:50051` — not `payment:50051`. The trace's ERROR log body confirms: `could not charge the card: ... badAddress:50051`.
>
> **Scope.** 100% of PlaceOrder attempts that reach the charge step are failing. Checkout returns `INTERNAL` to the frontend.
>
> **Handoff.** Escalate to the checkout service owner. Someone or something has configured checkout with the wrong payment address — either an environment variable override, a config push, or (in a fault-injection demo context) a feature-flag-driven code path. The fix is to restore the correct target address.

### Required evidence

| # | Tool | Query | What they should see |
|---|------|-------|----------------------|
| E1 | Prometheus | `sum(rate(rpc_client_call_duration_seconds_count{service_name="checkout", rpc_method="oteldemo.PaymentService/Charge", rpc_response_status_code="UNAVAILABLE"}[5m])) / sum(rate(rpc_client_call_duration_seconds_count{service_name="checkout", rpc_method="oteldemo.PaymentService/Charge"}[5m]))` | > 0.5 — confirms alert |
| E2 | Jaeger | `service=checkout error=true` last 15m | Dozens of matching traces |
| E3 | Jaeger | Open any failing trace; inspect `oteldemo.PaymentService/Charge` child span | `rpc.grpc.status_code=14` (UNAVAILABLE); `server.address=badAddress:50051` |
| E4 | OpenSearch | `resource.service.name.keyword:checkout AND severity.text:ERROR` | ERROR log: `could not charge the card: ... badAddress:50051` |
| E5 | Jaeger (sanity check) | `service=payment` last 15m | Zero recent traces (payment is idle — no one is reaching it) |

### Red herrings (minimal — alert is prescriptive)

| Hypothesis | Evidence | Why it's wrong |
|---|---|---|
| **Payment is down** | Jaeger shows zero recent payment traces. Grafana payment dashboard shows zero request rate. | Payment isn't down — nothing is *reaching* it. The problem is on the caller side. |
| **Network partition** | Other checkout dependencies (cart, shipping, currency, product-catalog) all show healthy `OK` spans in the same traces. | Only the payment call fails. Not a network-wide issue. |
| **DNS outage** | Other services resolve fine. | DNS is working — the target hostname `badAddress:50051` is wrong, not unreachable. |

### Keywords the grader looks for

**Required:**
- `badAddress` OR `badAddress:50051` (the literal wrong address)
- `UNAVAILABLE` (the gRPC status)
- `checkout` (the failing caller)
- `payment` OR `oteldemo.PaymentService/Charge` (the target)

**Strongly expected:**
- `misconfigured` / `wrong address` / `wrong target` (the diagnosis)
- Reference to the trace's `server.address` or the ERROR log body

**Acceptable but not required:**
- Speculation about *why* checkout has the wrong address (feature flag, env var, config push) — that's for the owner, not the on-call responder

### Out-of-scope conclusions

- **"I checked the flag file and saw `paymentUnreachable=on`."** → TM-A violation. Flag for re-training.
- **"Payment service is dead."** → Misdiagnosis. Payment is healthy; no one is reaching it.
- **"It's a DNS outage."** → Misdiagnosis. Other services resolve fine.

### Time-to-solve budget

- **Target: under 15 minutes.**
- Longer than 30 minutes: coach on reading the alert `summary` carefully — this case is a gift.

---

## Case 3 — `ResourceUtilizationWarning` (IMPOSSIBLE / Terminal)

### Alert payload as delivered to the trainee

```yaml
alert: ResourceUtilizationWarning
severity: warning
scenario: case3

summary: |
  product-reviews memory elevated (>80% of container limit) — limited forensic data available

description: |
  product-reviews container memory usage has exceeded 80% of its limit for 5 minutes.
  Investigative steps you may attempt:
  1. Inspect process_memory_usage_bytes{service_name="product-reviews"} trend — this WILL show a monotonic climb.
  2. Inspect traces_span_metrics_calls_total{service_name="product-reviews", status_code="STATUS_CODE_ERROR"} — this WILL NOT show elevated errors (see service_map.yml: productreviews.logs: null; only SPAN_KIND_CLIENT flagd reconnect errors are recorded).
  3. Query OpenSearch otel-logs-* for resource.service.name.keyword:"product-reviews" — this WILL NOT return records. The service does not log to OpenSearch by design (service_map.yml documents this gap).
  4. Inspect cpython_gc_* — this WILL NOT differentiate leak from baseline allocation.
  This scenario is intentionally unsolvable from telemetry alone.
```

### Expected first-read reaction

"Memory leak on product-reviews. Alert literally says 'limited forensic data available.' Let me try the four steps it lists and see."

### Canonical RCA narrative (the *correct* trainee response is to give up on telemetry and escalate)

> **What I can say from telemetry.** The `product-reviews` container's process memory (`process_memory_usage_bytes`) has grown monotonically at roughly 30–40 MB/min over the last 15 minutes, breaching 80% of its 500 MB container limit. There are no ERROR-severity spans. OpenSearch returns zero documents for this service under any query (the service does not log to OpenSearch — this is a pre-existing gap documented in the system's service map, not a broken exporter). Python GC metrics show baseline behavior. Memory growth does **not** correlate with request rate: at high load and at low load, memory rises at the same rate, so the leak is not driven by inbound gRPC traffic.
>
> **What I cannot say from telemetry alone.** I cannot identify which object, code path, or dependency is retaining memory. I have no logs with request context, no per-request attributes on server spans, and no labeled memory metric that distinguishes this leak from legitimate working-set growth. The four investigative steps enumerated in the alert description have all been exhausted with no actionable lead.
>
> **Handoff.** Escalate to the product-reviews service owner. Request: (a) a live heap profile or memory snapshot of the running container, (b) temporary deployment of a patched image that adds request-scoped logging and per-handler memory instrumentation, (c) review of any background threads or timers inside the service that might be independent of request handling. In the meantime, as mitigation, request a rolling restart of `product-reviews` every 45 minutes until a root cause is identified.
>
> **Training takeaway.** *You cannot debug what you do not log.* This alert fired honestly and told me exactly how deep the forensic surface goes. The correct response to a terminal alert is to recognize the ceiling, escalate with a clear ask, and apply a mitigation — not to dig indefinitely.

### Required evidence

| # | Tool | Query | What they should see |
|---|------|-------|----------------------|
| E1 | Prometheus | `process_memory_usage_bytes{service_name="product-reviews"}` graphed over last 30m | Monotonic climb; crosses 400 MB (80% of 500 MB limit) |
| E2 | Prometheus | `traces_span_metrics_calls_total{service_name="product-reviews", status_code="STATUS_CODE_ERROR", span_kind="SPAN_KIND_SERVER"}` | Zero (or baseline rate — no elevation) |
| E3 | OpenSearch (via Grafana) | `resource.service.name.keyword:"product-reviews"` last 1h | Zero documents |
| E4 | Prometheus | `rate(cpython_gc_collections_total{service_name="product-reviews"}[5m])` and `rate(cpython_gc_collected_objects_total{service_name="product-reviews"}[5m])` | Baseline rates — no anomaly |
| E5 | Prometheus (the correlation check a good trainee tries) | Memory (E1) plotted against `rate(traces_span_metrics_calls_total{service_name="product-reviews", span_kind="SPAN_KIND_SERVER"}[1m])` | No correlation visible; memory climbs the same whether request rate is high or low |

### Red herrings (or rather, "dead ends the trainee will walk into")

| Hypothesis | Evidence | Why it's a dead end |
|---|---|---|
| **Leak scales with traffic → it's per-request state in a handler** | Plot memory vs request rate | No correlation. Leak rate is flat across request levels. |
| **GC is broken** | `cpython_gc_*` metrics | GC is running normally. It just has nothing collectable to free. |
| **Another Python service (recommendation) is also leaking** | Compare `process_memory_usage_bytes{service_name="recommendation"}` to product-reviews | Recommendation is flat. Only product-reviews climbs. |
| **Container restart would reveal log output on startup** | Trainee cannot restart containers under TM-A | No action available. |

### Keywords the grader looks for

**Required (must be present — recognizing the terminal nature is the correct outcome):**
- `cannot` / `unable` / `insufficient` / `limited` (acknowledgment of the forensic ceiling)
- `heap profile` / `memory snapshot` / `add logging` / `patched image` (the correct ask in the handoff)
- `escalate` / `service owner` (recognizing this is a handoff, not a self-solve)

**Strongly expected:**
- Acknowledgment that the alert's four investigative steps were all tried
- The observation that memory is **not correlated** with request rate
- The phrase "no logs" or equivalent recognition that OpenSearch is empty for this service

**Bonus (indicates sophistication):**
- Mention of "background thread" / "timer" / "scheduled task" as a hypothesis (they won't confirm it from telemetry, but raising it shows they understand why the leak decorrelates)
- A mitigation proposal (rolling restart cadence) alongside the escalation

### Out-of-scope conclusions (all of these mean the trainee either cheated or misdiagnosed)

- **"I read `src/product-reviews/product_reviews_server.py` and found the leak."** → TM-A violation.
- **"I docker exec'd into the container and ran `py-spy`."** → TM-A violation.
- **"The leak is caused by `GetProductReviews` handler retaining payloads."** → Without telemetry evidence this is a guess; and it's wrong anyway (the leak is in a background thread, not a handler).
- **"The root cause is the `productReviewsMemoryLeak` flag."** → TM-A violation (would require flag-file or flagd-ui access).
- **"Declared the incident resolved without escalating."** → Worst outcome. The trainee should have escalated with a specific ask.

### Time-to-solve budget

- **No upper bound on investigation time** — but the trainee should reach the "escalate with a specific ask" conclusion within **30–60 minutes** of the alert firing.
- If the trainee marks this as `solved` from telemetry alone, the scenario controller emits an error (Req 13.4). Either they cheated or they're asserting a conclusion they can't support.
- The correct "solve" is: "I exhausted the available signals, I cannot identify the root cause from telemetry, here is the handoff."

---

## Cross-case grading summary

| Metric | Case 1 | Case 2 | Case 3 |
|---|---|---|---|
| Alert tier | Deceptive | Prescriptive | Terminal |
| Target time-to-diagnosis | 45–90 min | < 15 min | 30–60 min (to escalation) |
| Primary investigation tool | Jaeger (deep trace descent) | Jaeger + OpenSearch (shallow) | Prometheus (dead ends) + cognitive recognition |
| Number of MLT hops to root cause | 4 (checkout → shipping → quote → `calculate-quote` events) | 1 (trace attribute) | ∞ (no path exists) |
| Expected handoff recipient | Quote service owner | Checkout service owner | Product-reviews service owner + heap profile request |
| Correct "solved" outcome | Names the `numberOfItems` exception on `calculate-quote` | Names `badAddress:50051` | Names the forensic ceiling and asks for out-of-band instrumentation |

## How to use this document

- **Before a training session:** share the alert payloads only (not the RCA narratives or keywords) with anyone who will receive the pager. The "Alert payload as delivered to the trainee" section of each case is the *only* thing a trainee should see before their investigation.
- **During a session:** the Training_Coordinator uses the Required Evidence table to check whether the trainee found the right signals (without telling them).
- **After a session:** grade the trainee's write-up against the Keywords and Out-of-scope sections. A good write-up hits all Required keywords, most Strongly Expected keywords, and none of the Out-of-scope conclusions.
- **For the RCA agent:** the Required Evidence tables are the positive training targets; the Out-of-scope Conclusions are the negative examples. A well-behaved RCA agent should produce text that scores ≥80% on Required keywords and 0% on Out-of-scope conclusions.
