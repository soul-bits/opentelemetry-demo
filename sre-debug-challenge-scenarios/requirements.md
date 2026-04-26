# Requirements Document

## Introduction

This feature delivers three deliberately-crafted fault injection scenarios for the OpenTelemetry Demo (astronomy e-commerce microservices), designed as a calibrated training environment for SRE and QA engineers practicing Root Cause Analysis (RCA) from Metrics, Logs, and Traces (MLT).

**Each scenario begins with exactly one Prometheus alert firing. The alert is the SRE_Trainee's sole entry point — they have no other signal that a scenario is active.** The *informational content of the alert itself* is the primary difficulty dial across the three cases:

- **Case 1 alert is DECEPTIVE (HARD)** — fires on a real downstream symptom but its labels and summary deliberately point the trainee toward the wrong subsystem. A conscientious SRE who reads the alert carefully will still waste 30+ minutes before pivoting to the actual root cause four hops upstream in the PHP quote service.
- **Case 2 alert is PRESCRIPTIVE (EASY)** — names the failing RPC method and service in its summary. A competent SRE reaches root cause in under 15 minutes by literally following the alert text into Jaeger and OpenSearch.
- **Case 3 alert is TERMINAL (IMPOSSIBLE)** — describes a real, valid symptom (elevated container memory on `product-reviews`) but the underlying service emits no correlatable forensic signal. The alert is where the investigation starts *and ends* from telemetry alone.

The scenarios are activated by feature flags where possible, coexist with the existing demo fault-injection flags, and are fully reversible without corrupting long-term state (astronomy-db, OpenSearch indexes, Kafka topics).

## Architecture Ground Truth (normative)

This feature targets the `docker-compose.minimal.yml` stack (per `CLAUDE.md`). The following services are **active** and in scope: `frontend`, `frontend-proxy` (Envoy), `load-generator` (Locust), `cart` + `valkey-cart`, `checkout`, `product-catalog` + `astronomy-db` (PostgreSQL), `product-reviews`, `recommendation`, `currency`, `shipping`, `quote`, `payment`, `flagd`, `otel-collector`, `jaeger`, `prometheus`, `alertmanager`, `grafana`, `opensearch`. The following services are **commented out** in the minimal compose and SHALL be considered unavailable for scenario design: `ad`, `email`, `image-provider`, `flagd-ui`, `llm`, `kafka`, `accounting`, `fraud-detection`. Case_1 therefore does not rely on Kafka/accounting/fraud-detection evidence trails, and Case_3 scopes its leak to the two Product_Reviews handlers that do not transit the disabled LLM.

The canonical telemetry contract for each active service — metrics families, label dimensions, log severity fields, log index patterns, trace operation names, and the documented gaps (notably `productreviews.logs: null`) — is defined in `service_map.yml`, which is normative for this feature and for the QA_Engineer observability validator.

## Threat Model for the SRE_Trainee (normative)

All three scenarios assume **Threat Model A (TM-A)**: the SRE_Trainee has interactive access to Prometheus (`:9090`), Alertmanager (`:9093`), Grafana (`:3000`), Jaeger (`:16686`), and the OpenSearch `otel-logs-*` index via Grafana's OpenSearch datasource, and can issue arbitrary PromQL, OpenSearch DSL, and Jaeger queries; and does **NOT** have read access to the repository source, the flagd JSON file, the Prometheus rule file, docker-compose files, the flagd-ui, any container shell, or any non-ingested data store (e.g., `pg_stat_activity`). Every acceptance criterion in this document that references an SRE_Trainee observation is satisfiable within this threat model. Acceptance criteria that reference filesystem or flagd-ui inspection by the SRE_Trainee (notably Requirement 8.5) are **vacuously satisfied** under TM-A and are retained for auditability in deployments that expose those surfaces.

## Glossary

- **Alert_Informational_Content**: The sum total of actionable information an alert provides to the SRE_Trainee via its name, labels, annotations.summary, annotations.description, and runbook_url. Low informational content forces deeper investigation; high informational content shortens the path to root cause.
- **Deceptive_Alert**: An alert whose informational content, while technically accurate, suggests a misleading initial hypothesis about the root cause. Used in Case_1.
- **Prescriptive_Alert**: An alert whose informational content literally names the failing component and failure mode, enabling a direct walk from alert to root cause. Used in Case_2.
- **Terminal_Alert**: An alert that describes a valid symptom but whose underlying subject service emits no correlatable forensic signal beyond the symptom itself. Used in Case_3.
- **Scenario**: One of the three fault-injection training cases (Case_1, Case_2, Case_3).
- **Training_Coordinator**: The human operator who activates, verifies, and tears down scenarios for an SRE training session.
- **SRE_Trainee**: The on-call engineer being trained; their interaction begins when a Prometheus alert fires.
- **QA_Engineer**: The engineer validating that the demo's observability coverage matches the documented `service_map.yml` contract and that scenarios expose the documented telemetry gaps.
- **Scenario_Controller**: The software component (scripts plus flagd configuration plus Prometheus alert rule file) that enables, disables, and verifies a Scenario.
- **Activation_Mechanism**: The specific lever used to enable a Scenario — a flagd feature flag toggle, an environment variable applied via container restart, or an alert-rules file reload.
- **MLT_Surface**: The combined queryable telemetry available to the SRE_Trainee: Prometheus metrics (port 9090), OpenSearch logs (`otel-logs-*` index), and Jaeger traces (port 16686).
- **RCA_Path**: The documented correct sequence of MLT_Surface queries that leads from the firing alert to the injected root cause.
- **Red_Herring_Path**: A documented plausible-but-incorrect line of investigation that a Scenario intentionally suggests.
- **Verification_Playbook**: The set of commands and queries the Training_Coordinator runs to confirm a Scenario is active and the expected MLT signals are present.
- **Teardown_Procedure**: The reversible sequence that restores the demo to a healthy baseline after a Scenario run.
- **Silent_Corruption**: Data corruption that produces no error status codes, no elevated error-rate metrics, and no ERROR/WARN log entries on the hot path.
- **Quote_Service**: The PHP service at `src/quote/app/routes.php` whose `calculateQuote()` function is the root cause of Case_1.
- **Shipping_Service**: The Rust service at `src/shipping/src/shipping_service.rs` that forwards quote values downstream.
- **Checkout_Service**: The Go service at `src/checkout/main.go` that orchestrates order placement.
- **Payment_Service**: The Node.js service at `src/payment/charge.js`.
- **Product_Reviews_Service**: The Python service at `src/product-reviews/product_reviews_server.py` that is the site of the Case_3 memory leak.
- **Flagd**: The OpenFeature flag daemon driven by `src/flagd/demo.flagd.json`, reloadable at runtime.
- **Baseline**: The state of the demo in which no training-scenario alert fires and order flow is healthy.
- **Scenario_Specific_Alert**: A Prometheus alert rule introduced by this feature, distinguishable from baseline alerts by a `scenario` label.
- **Case_1_Alert**: `AnomalousZeroValueOrders` — the Deceptive_Alert for Case_1.
- **Case_2_Alert**: `PaymentServiceUnreachable` — the Prescriptive_Alert for Case_2 (replaces the existing vague `SomethingWrongHere` alert).
- **Case_3_Alert**: `ProductReviewsMemoryHigh` — the Terminal_Alert for Case_3.
- **PBT**: Property-Based Test — automated correctness property executed with randomized inputs to verify scenario invariants.

## Requirements

### Requirement 1: The alert is the sole entry point and its informational content defines difficulty

**User Story:** As a Training_Coordinator, I want each scenario's difficulty to be primarily a function of how much actionable information the firing alert gives the SRE_Trainee, so that I can calibrate training by tuning the alert text itself rather than by hiding signals elsewhere in the MLT surface.

#### Acceptance Criteria

1. WHEN a Scenario is active, THE only notification the SRE_Trainee SHALL receive is the single corresponding Scenario_Specific_Alert firing in Prometheus or Grafana, and THE SRE_Trainee SHALL NOT be given any out-of-band hint about which Scenario is active.
2. THE Case_1_Alert `AnomalousZeroValueOrders` SHALL qualify as a Deceptive_Alert: its `annotations.summary` SHALL describe only the downstream symptom (zero-value shipping costs on placed orders) AND SHALL NOT name the Quote_Service, the PHP runtime, the `numberOfItems` field, the `calculate-quote` span, or the Shipping_Service as the subject of the anomaly.
3. THE Case_1_Alert `annotations.description` SHALL additionally include at least one plausible-but-wrong hypothesis phrased as a hint (for example, "verify payment service health" or "check checkout arithmetic"), steering the SRE_Trainee toward a Red_Herring_Path on first read.
4. THE Case_2_Alert `PaymentServiceUnreachable` SHALL qualify as a Prescriptive_Alert: its `annotations.summary` SHALL include the literal string `oteldemo.PaymentService/Charge`, the literal string `checkout`, and the literal gRPC status substring `UNAVAILABLE`.
5. THE Case_2_Alert `annotations.description` SHALL include a direct Jaeger search query hint formatted as `service=checkout error=true` AND an OpenSearch query hint formatted as `resource.service.name.keyword:checkout AND severity.text:ERROR`.
6. THE Case_3_Alert `ProductReviewsMemoryHigh` SHALL qualify as a Terminal_Alert: its `annotations.summary` SHALL describe the memory symptom on the `product-reviews` container AND SHALL explicitly disclaim investigative depth by including the substring "limited forensic data available".
7. THE Case_3_Alert `annotations.description` SHALL enumerate the exact investigative steps the SRE_Trainee may attempt (inspect `process_memory_usage_bytes` trend, inspect `traces_span_metrics_*` for errors, query OpenSearch `otel-logs-*` for the service) AND SHALL state for each step whether that step will or will not produce actionable data, so the Terminal nature of the scenario is discoverable from the alert after honest effort.
8. THE Prometheus alert rules file SHALL NOT carry an `annotations.runbook_url` for any Scenario_Specific_Alert; THE alert `annotations.description` field SHALL serve as the self-contained entry-point document for the SRE_Trainee and SHALL contain the full investigation guidance required by Requirements 1.3, 1.5, and 1.7 without delegating to an external page. (Amendment: earlier drafts of this feature proposed external runbook pages; that approach was dropped because the `description` field already carries sufficient guidance and because hosting external markdown pages adds deployment complexity without increasing training value.)
9. THE requirements deliverable SHALL include a table mapping alert tier to expected SRE_Trainee first-read reaction: Case_1 "suspect payment or checkout arithmetic"; Case_2 "payment service unreachable, open Jaeger"; Case_3 "memory leak on product-reviews, origin unclear".

### Requirement 2: Training_Coordinator activates scenarios via a single command

**User Story:** As a Training_Coordinator, I want to activate any one of the three scenarios with a single command, so that I can quickly set up a training session without editing multiple configuration files by hand.

#### Acceptance Criteria

1. THE Scenario_Controller SHALL expose a CLI entry point that accepts a scenario identifier from the set {`case1`, `case2`, `case3`} and an action from the set {`activate`, `verify`, `teardown`}.
2. WHEN the Training_Coordinator invokes activation for `case1`, THE Scenario_Controller SHALL enable a `quoteSilentCorruption` feature flag in `src/flagd/demo.flagd.json` and SHALL reload the flagd configuration without restarting any application container.
3. WHEN the Training_Coordinator invokes activation for `case2`, THE Scenario_Controller SHALL set the `paymentUnreachable` flag's `defaultVariant` to `on` in `src/flagd/demo.flagd.json` and SHALL reload the flagd configuration without restarting any application container.
4. WHEN the Training_Coordinator invokes activation for `case3`, THE Scenario_Controller SHALL enable a `productReviewsMemoryLeak` feature flag in `src/flagd/demo.flagd.json` and SHALL reload the flagd configuration without restarting any application container.
5. WHEN the Training_Coordinator invokes activation for any scenario, THE Scenario_Controller SHALL ensure the corresponding Scenario_Specific_Alert rule is present in the Prometheus alert-rules file AND SHALL trigger a Prometheus configuration reload via `POST http://prometheus:9090/-/reload` within 5 seconds of flag toggle.
6. WHEN the Training_Coordinator invokes activation for any scenario, THE Scenario_Controller SHALL print to standard output (a) the scenario identifier, (b) the expected alert name, (c) the expected time-to-fire in seconds, and (d) the URL of the flagd-ui with the relevant flag pre-selected.
7. IF activation of a scenario fails at any step, THEN THE Scenario_Controller SHALL roll back any partial state changes made during that activation AND SHALL exit with a non-zero status code and an error message naming the failed step.
8. WHEN the Training_Coordinator invokes activation twice in a row for the same scenario, THE Scenario_Controller SHALL produce the same observable outcome on the second invocation as on the first (idempotent activation).

### Requirement 3: Case 1 — HARD scenario injects silent $0 quote corruption

**User Story:** As a Training_Coordinator, I want Case_1 to inject a silent corruption in the Quote_Service that produces $0 shipping values downstream without generating error rates or error logs, so that the SRE_Trainee must correlate traces across four hops to find the root cause.

#### Acceptance Criteria

1. WHILE the `quoteSilentCorruption` flag is `on`, THE Quote_Service SHALL, for a random fraction of inbound `POST /getquote` requests in the range 20% to 40% inclusive, behave as if the inbound JSON body lacks the `numberOfItems` key: it SHALL throw `\InvalidArgumentException('numberOfItems not provided')` inside `calculateQuote()`, SHALL catch the exception via `$childSpan->recordException($exception)` so that the `calculate-quote` INTERNAL span carries an `exception` event whose `exception.message` attribute contains the substring `numberOfItems`, AND SHALL return HTTP 200 with body `0` to the caller.
2. THE Case_1 injection SHALL be flag-gated entirely inside `src/quote/app/routes.php` via an OpenFeature boolean flag evaluation performed once per inbound request; no environment variable SHALL be required and no container other than `quote` SHALL need to be restarted to activate Case_1.
3. WHILE Case_1 is active, THE Shipping_Service SHALL continue to return HTTP 200 to Checkout_Service for every corrupted request, with a `cost_usd` Money value whose `units == 0` and `nanos == 0`.
4. WHILE Case_1 is active, THE Checkout_Service SHALL successfully complete `PlaceOrder` for every corrupted request, charge the Payment_Service for the corrupted total, return gRPC status `OK`, AND THE PlaceOrder server span SHALL carry the attribute `app.shipping.amount` with a float value less than `1.00` (as set in `main.go` at the `span.SetAttributes(...)` site following `shipOrder`).
5. WHILE Case_1 is active, THE metric `rpc_server_call_duration_seconds_count{service_name="checkout", rpc_method="oteldemo.CheckoutService/PlaceOrder", rpc_response_status_code!="OK"}` SHALL NOT increase above its Baseline 5-minute rolling rate.
6. WHILE Case_1 is active, THE OpenSearch index `otel-logs-*` SHALL contain zero log entries with `severity.text IN (ERROR, WARN, error, warn, Error, Warning)` AND `resource.service.name.keyword IN (checkout, shipping, quote, currency, payment, cart)` that are attributable to the corrupted orders.
7. WHERE a Jaeger trace contains a corrupted order, THE trace SHALL include a span named `calculate-quote` on `service_name="quote"` whose events include an event named `exception` whose `exception.message` attribute contains the substring `numberOfItems`.
8. WHERE a Jaeger trace contains a corrupted order, THE root span for `oteldemo.CheckoutService/PlaceOrder` SHALL carry attributes `app.order.amount` and `app.shipping.amount` whose float values are both less than `1.00`.
9. WHILE Case_1 is active, THE Checkout_Service SHALL export a new counter metric `app_order_shipping_cost_usd_total{service_name="checkout", bucket="zero"}` incremented once per `PlaceOrder` whose computed `shippingCostFloat < 1.00`, AND the same counter with `bucket="nonzero"` SHALL be incremented otherwise; this counter is introduced by Case_1 to make the downstream symptom PromQL-observable without relying on span attributes that Prometheus does not ingest.

### Requirement 4: Case 1 — Deceptive Alert fires on downstream anomaly

**User Story:** As a Training_Coordinator, I want the Case_1 alert to fire on an anomalous downstream symptom and to actively mislead the SRE_Trainee toward the wrong subsystem, so that the SRE_Trainee must do real RCA rather than follow the alert text to the answer.

#### Acceptance Criteria

1. THE Prometheus alert rules file SHALL define an alert named `AnomalousZeroValueOrders` whose PromQL expression computes the 5-minute rolling ratio `sum(rate(app_order_shipping_cost_usd_total{service_name="checkout", bucket="zero"}[5m])) / sum(rate(app_order_shipping_cost_usd_total{service_name="checkout"}[5m]))` AND SHALL fire when that ratio exceeds `0.15` for `2m`.
2. THE `AnomalousZeroValueOrders` alert SHALL carry the label `severity=warning` AND the label `scenario=case1`.
3. THE `AnomalousZeroValueOrders` alert `annotations.summary` SHALL be of the form "Elevated rate of zero-value orders detected in checkout — possible payment or pricing issue" AND SHALL NOT contain any of the substrings "quote", "PHP", "numberOfItems", "calculate-quote", "shipping service", or "Rust".
4. THE `AnomalousZeroValueOrders` alert `annotations.description` SHALL suggest at least one Red_Herring_Path as a hint, using wording such as "Investigate payment service charge logic" or "Verify checkout arithmetic for cart totals".
5. WHEN the `quoteSilentCorruption` flag transitions from `off` to `on` under sustained load from the load-generator, THE `AnomalousZeroValueOrders` alert SHALL fire within 5 minutes.
6. WHEN the `quoteSilentCorruption` flag transitions from `on` to `off` under sustained load, THE `AnomalousZeroValueOrders` alert SHALL return to the non-firing state within 10 minutes.
7. WHILE Case_1 is active, THE metric `ALERTS{alertname="AnomalousZeroValueOrders", alertstate="firing"}` SHALL be equal to `1`.

### Requirement 5: Case 1 — RCA path is documented and traversable

**User Story:** As an SRE_Trainee debugging Case_1, I want a documented expected RCA path that walks from the firing alert through checkout traces, shipping spans, quote server spans, and into the internal `calculate-quote` span events, so that a trained SRE can reach the root cause in 45 to 90 minutes.

#### Acceptance Criteria

1. THE requirements deliverable for Case_1 SHALL document an RCA_Path consisting of, in order: (a) observing the `AnomalousZeroValueOrders` alert in Grafana or Prometheus, (b) querying traces-span-metrics or Jaeger for PlaceOrder traces with `app.shipping.amount < 1.0` in the last 5 minutes, (c) opening a matching trace in Jaeger and inspecting the checkout `PlaceOrder` span's `app.shipping.amount` attribute, (d) descending into the child `POST /get-quote` client span on Checkout_Service, (e) descending into the Shipping_Service `POST /get-quote` server span, (f) descending into the `POST /getquote` Quote_Service server span, (g) descending into the internal `calculate-quote` span, and (h) reading the `exception.message` span event that contains the substring `numberOfItems`.
2. THE requirements deliverable for Case_1 SHALL document at least four Red_Herring_Paths, each including the plausible hypothesis, the query the SRE_Trainee would run, and the specific signal that disproves it.
3. THE four Red_Herring_Paths SHALL include at minimum: (a) Payment_Service failure hypothesis, (b) Checkout_Service arithmetic bug hypothesis, (c) Currency_Service zero-rate hypothesis, and (d) Cart_Service zero-quantity hypothesis.
4. THE requirements deliverable for Case_1 SHALL document a Verification_Playbook containing (a) a PromQL query that confirms zero-value order rate is elevated, (b) an OpenSearch query that confirms absence of ERROR/WARN logs on checkout and quote services, and (c) a Jaeger search URL that returns a trace containing a `calculate-quote` span with an `exception.message` event.
5. THE requirements deliverable for Case_1 SHALL document a Teardown_Procedure that (a) sets `quoteSilentCorruption` to `off`, (b) confirms alert resolution within 10 minutes, AND (c) requires no container restarts (flag change is hot-reloaded by flagd).

### Requirement 6: Case 2 — EASY scenario produces a clearly-described payment outage

**User Story:** As a Training_Coordinator, I want Case_2 to toggle the existing `paymentUnreachable` flag so the Checkout_Service connects to `badAddress:50051`, and I want the alert to be a Prescriptive_Alert, so that an experienced SRE_Trainee can reach the root cause in under 15 minutes by following the alert text into MLT signals.

#### Acceptance Criteria

1. WHILE the `paymentUnreachable` flag is `on`, THE Checkout_Service SHALL, within the `chargeCard` code path at `src/checkout/main.go`, replace its payment gRPC client with a client connected to the literal address `badAddress:50051`.
2. WHILE Case_2 is active, THE Checkout_Service SHALL emit gRPC client spans for `oteldemo.PaymentService/Charge` carrying status code `UNAVAILABLE`.
3. WHILE Case_2 is active, THE Checkout_Service SHALL emit ERROR-severity log entries in `otel-logs-*` whose body contains both the substrings "could not charge the card" AND "badAddress:50051".
4. WHILE Case_2 is active, THE metric `rpc_client_call_duration_seconds_count{service_name="checkout", rpc_method="oteldemo.PaymentService/Charge", rpc_response_status_code="UNAVAILABLE"}` SHALL be greater than zero AND SHALL exceed the OK-status count for the same method over any 5-minute rolling window.
5. THE Prometheus alert rules file SHALL define an alert named `PaymentServiceUnreachable` whose expression detects that more than 50% of `oteldemo.PaymentService/Charge` calls from `service_name="checkout"` have `rpc_response_status_code="UNAVAILABLE"` over a 5-minute window, AND SHALL fire with `for: 1m`.
6. THE `PaymentServiceUnreachable` alert SHALL carry `severity=critical`, `scenario=case2`, AND an `annotations.summary` matching Requirement 1.4 (containing `oteldemo.PaymentService/Charge`, `checkout`, and `UNAVAILABLE`).
7. WHEN the `paymentUnreachable` flag transitions from `off` to `on` under sustained load, THE `PaymentServiceUnreachable` alert SHALL fire within 2 minutes.
8. THE requirements deliverable for Case_2 SHALL document an RCA_Path consisting of, in order: (a) reading the `PaymentServiceUnreachable` alert summary, (b) opening Jaeger and searching `service=checkout error=true`, (c) opening a matching trace and reading the red `oteldemo.PaymentService/Charge` child span's `rpc.grpc.status_code=UNAVAILABLE` along with its `server.address` or `peer.address` attribute showing the literal string `badAddress:50051`, (d) opening the trace's logs panel to find the ERROR entry whose body contains both `could not charge the card` and `badAddress:50051`, and (e) formulating the handoff ticket: "Checkout is dialing `badAddress:50051` instead of `payment:50051`; escalate to the checkout service owner with trace IDs." THE RCA_Path SHALL NOT require the SRE_Trainee to open any file in the repository, any flagd UI, or any surface outside Prometheus / Alertmanager / Grafana / Jaeger / OpenSearch.
9. THE requirements deliverable for Case_2 SHALL document a Teardown_Procedure that sets `paymentUnreachable` to `off` AND confirms alert resolution within 3 minutes.
10. THE existing `SomethingWrongHere` alert rule in `src/prometheus/alert-rules.yml` SHALL be replaced in-place by the new `PaymentServiceUnreachable` rule defined in Requirement 6.5, AND the replacement SHALL leave all other alerts in the file unchanged.

### Requirement 7: Case 3 — IMPOSSIBLE scenario leaks memory with no forensic surface

**User Story:** As a Training_Coordinator, I want Case_3 to inject a memory leak into the Product_Reviews_Service that produces no log entries and no request-level attributes, and I want the alert to be a Terminal_Alert that honestly describes the limited forensic surface, so that the SRE_Trainee learns firsthand why structured logging and attribute capture matter.

#### Acceptance Criteria

1. WHILE the `productReviewsMemoryLeak` flag is `on`, THE Product_Reviews_Service SHALL grow a module-level byte-buffer list at a fixed wall-clock cadence driven by a background daemon thread (1 MiB per 1.5–2.0 second tick, target rate ≈ 30–40 MiB/min) that is independent of inbound gRPC request handling; no `ProductReviewService/*` request handler body SHALL be modified by Case_3, and the leak rate SHALL NOT be a function of request arrival rate. THE `ProductReviewService/AskProductAIAssistant` handler remains out of scope for Case_3 because the `llm` container is disabled in `docker-compose.minimal.yml`.
2. WHILE Case_3 is active, THE metric `process_memory_usage_bytes{service_name="product-reviews"}` SHALL increase monotonically (no decrease greater than 5% per 1-minute window) over any 10-minute rolling window.
3. WHILE Case_3 is active, THE OpenSearch index `otel-logs-*` SHALL contain zero log entries with `resource.service.name.keyword="product-reviews"` throughout the leak window.
4. WHILE Case_3 is active, THE Product_Reviews_Service SHALL continue returning successful responses to `ProductReviewService/GetProductReviews` and `ProductReviewService/GetAverageProductReviewScore`, AND THE metric `traces_span_metrics_calls_total{service_name="product-reviews", status_code="STATUS_CODE_ERROR", span_kind="SPAN_KIND_SERVER"}` SHALL NOT increase above its Baseline rate.
5. WHILE Case_3 is active, THE p95 latency derived from `traces_span_metrics_duration_milliseconds{service_name="product-reviews", span_kind="SPAN_KIND_SERVER"}` SHALL remain within 20% of its Baseline value.
6. WHILE Case_3 is active, THE metric `process_cpu_utilization_ratio{service_name="product-reviews"}` SHALL remain within 20% of its Baseline value.
7. THE Prometheus alert rules file SHALL define an alert named `ProductReviewsMemoryHigh` whose expression fires when the ratio of `process_memory_usage_bytes{service_name="product-reviews"}` to the `container_memory_usage_limit_bytes{container_name="product-reviews"}` gauge (derived from the `docker_stats` receiver) exceeds `0.80` for `5m`; IF the docker_stats-derived limit metric is unavailable under the deployment, THEN the alert expression MAY instead fire when `process_memory_usage_bytes{service_name="product-reviews"}` exceeds a static threshold of `400000000` bytes (80% of the 500M container limit defined in `docker-compose.minimal.yml`) for `5m`.
8. THE `ProductReviewsMemoryHigh` alert SHALL carry `severity=warning`, `scenario=case3`, AND an `annotations.summary` matching Requirement 1.6 (referencing "memory", the service name `product-reviews`, and the substring "limited forensic data available").
9. WHEN the `productReviewsMemoryLeak` flag transitions from `off` to `on` under sustained load, THE `ProductReviewsMemoryHigh` alert SHALL fire within 15 minutes.
10. THE requirements deliverable for Case_3 SHALL document the intentional telemetry gap: specifically (a) `service_map.yml` confirms `productreviews.logs: null`, (b) only `SPAN_KIND_CLIENT` spans with `status_code: STATUS_CODE_ERROR` are observable in span metrics and those are pre-existing flagd reconnect noise, (c) no request payload attributes are captured on server spans, and (d) `cpython_gc_*` metrics do not differentiate leak versus baseline allocation.
11. THE requirements deliverable for Case_3 SHALL explicitly state that the scenario is UNSOLVABLE from telemetry alone AND that the training takeaway is "you cannot debug what you do not log."
12. THE requirements deliverable for Case_3 SHALL document a Teardown_Procedure that (a) sets `productReviewsMemoryLeak` to `off`, (b) restarts only the `product-reviews` container to release the leaked module-global list, AND (c) confirms `process_memory_usage_bytes` returns to within 20% of Baseline within 5 minutes.
13. WHILE Case_3 is active, THE Pearson correlation coefficient between time-aligned 1-minute samples of `process_memory_usage_bytes{service_name="product-reviews"}` and `sum(rate(traces_span_metrics_calls_total{service_name="product-reviews", span_kind="SPAN_KIND_SERVER"}[1m]))` over any 10-minute rolling window SHALL have absolute value strictly less than `0.30` under any load level achievable by varying `LOCUST_USERS` in the range `0` to `50`; this acceptance criterion closes the Prometheus-side-channel correlation path that a trainee under TM-A might otherwise use to infer that the leak is request-driven.

### Requirement 8: SRE_Trainee consumes a self-contained runbook entry point

**User Story:** As an SRE_Trainee, I want each scenario to present me with a single alert as my on-call starting point and nothing else, so that my debugging experience faithfully simulates a real pager event.

#### Acceptance Criteria

1. WHEN a Scenario_Specific_Alert transitions to state `firing`, THE alert payload SHALL NOT contain any label or annotation that names the root-cause service, flag, or file (except where Requirement 1.4 explicitly allows for Case_2). THE alert SHALL NOT carry a `runbook_url` (per Requirement 1.8 as amended).
2. THE alert `annotations.description` SHALL itself serve as the self-contained entry-point document for the SRE_Trainee, describing the alert in the same terms as the alert name and summary AND providing the investigation guidance required per alert tier (Red_Herring_Path hints for Case_1, direct query hints for Case_2, enumerated WILL/WILL NOT steps for Case_3). No external landing page SHALL be required.
3. THE Grafana default dashboards SHALL NOT be modified by scenario activation, so that the SRE_Trainee sees the same unmodified dashboard set regardless of which scenario is active.
4. WHILE any scenario is active, THE flagd configuration at `src/flagd/demo.flagd.json` SHALL remain readable to the Training_Coordinator (not the SRE_Trainee) via the filesystem for live inspection; THE SRE_Trainee SHALL have no access to this file, to the `flagd-ui`, or to any other out-of-band mechanism for inferring the active flag set.
5. THE `quoteSilentCorruption`, `productReviewsMemoryLeak`, and `paymentUnreachable` flags SHALL, when active, carry a `description` containing the literal substring "Fault injection:" so that any operator with legitimate filesystem access to `src/flagd/demo.flagd.json` (Training_Coordinator, implementor, maintainer) can distinguish training fault flags from genuine feature flags; THE SRE_Trainee SHALL have no interaction with this field because they SHALL have no access to the file under TM-A.

### Requirement 9: QA_Engineer validates observability coverage matches service_map.yml

**User Story:** As a QA_Engineer, I want an automated validation that verifies `service_map.yml` accurately describes the telemetry each service emits (including the documented gaps for product-reviews), so that Case_3 reliably demonstrates a real observability hole rather than a misconfigured exporter.

#### Acceptance Criteria

1. THE feature SHALL include an automated validation suite named `service-map-observability-validator` executable via a single command.
2. THE validator SHALL, for each service entry in `service_map.yml`, query the live Prometheus HTTP API to confirm that every metric family declared under `metrics[*].name` exists with at least one time-series sample in the last 5 minutes.
3. THE validator SHALL, for each service entry whose `logs` field is not null, query the OpenSearch `otel-logs-*` index to confirm that at least one log record with the declared `service_name_field` equal to `service_name_value` has been ingested in the last 5 minutes.
4. THE validator SHALL, for each service entry whose `logs` field is `null`, query the OpenSearch `otel-logs-*` index to confirm that zero log records have been ingested for that service in the last 5 minutes, AND SHALL FAIL if any logs are found (because presence of logs would invalidate Case_3).
5. THE validator SHALL, for each service entry, query the Jaeger API to confirm that every operation declared under `traces.server_operations[*]` has at least one trace in the last 5 minutes.
6. IF the validator detects a discrepancy between `service_map.yml` and the live telemetry, THEN THE validator SHALL exit non-zero AND SHALL emit a report naming the service, the expected signal, and the observed signal.
7. THE validator SHALL complete in under 60 seconds on a warm demo environment running the Baseline.

### Requirement 10: Correctness properties hold under randomized load

**User Story:** As a QA_Engineer, I want property-based tests that validate scenario-specific invariants under randomized order payloads and timing, so that I can trust each scenario produces the intended observable behavior every run.

#### Acceptance Criteria

1. THE feature SHALL include a property-based test suite exercising each scenario with randomized PlaceOrder requests drawn from the live load generator's observed domain (cart item quantities from the discrete set {1, 2, 3, 4, 5, 10}, product IDs from the ten astronomy SKUs in `src/load-generator/locustfile.py`, default currency USD unless the frontend session currency is overridden, randomized user UUIDs).
2. WHILE Case_1 is active, THE property `checkout_error_rate_at_baseline` SHALL hold: for any randomized 5-minute window under sustained load, `sum(rate(rpc_server_call_duration_seconds_count{service_name="checkout", rpc_method="oteldemo.CheckoutService/PlaceOrder", rpc_response_status_code!="OK"}[5m]))` divided by `sum(rate(rpc_server_call_duration_seconds_count{service_name="checkout", rpc_method="oteldemo.CheckoutService/PlaceOrder"}[5m]))` SHALL be less than `0.01`.
3. WHILE Case_1 is active, THE property `zero_shipping_reaches_downstream` SHALL hold: for any randomized 5-minute window under sustained load, there SHALL exist at least one trace whose `oteldemo.CheckoutService/PlaceOrder` server span has `app.order.amount == app.shipping.amount` AND `app.shipping.amount < 1.00`.
4. WHILE Case_2 is active, THE property `alert_fires_within_two_minutes` SHALL hold: for any activation, `ALERTS{alertname="PaymentServiceUnreachable", alertstate="firing"} == 1` SHALL become true within 120 seconds of the flag transition.
5. WHILE Case_2 is active, THE property `trace_error_within_alert_window` SHALL hold: for any activation, within the same 2-minute window measured from flag transition, at least one Jaeger trace SHALL exist where `service=checkout`, `error=true`, AND a child span named `oteldemo.PaymentService/Charge` carries `rpc.grpc.status_code=UNAVAILABLE`.
6. WHILE Case_3 is active, THE property `no_logs_for_product_reviews` SHALL hold: for any randomized 10-minute leak window, zero log records SHALL exist in `otel-logs-*` with `resource.service.name.keyword="product-reviews"`.
7. WHILE Case_3 is active, THE property `memory_monotonically_increasing_and_rate_decorrelated` SHALL hold: for any randomized 10-minute leak window, (a) the linear regression slope of `process_memory_usage_bytes{service_name="product-reviews"}` sampled at 15-second resolution SHALL be strictly positive, AND (b) the Pearson correlation coefficient between those memory samples and time-aligned samples of `sum(rate(traces_span_metrics_calls_total{service_name="product-reviews", span_kind="SPAN_KIND_SERVER"}[1m]))` SHALL have absolute value strictly less than `0.30` across randomized `LOCUST_USERS` levels in the range `0` to `50`.
8. WHILE no scenario is active, THE property `clean_baseline` SHALL hold: `ALERTS{alertname=~"AnomalousZeroValueOrders|PaymentServiceUnreachable|ProductReviewsMemoryHigh"}` SHALL return zero firing series for any randomized 5-minute Baseline window.

### Requirement 11: Scenarios are reversible, idempotent, and non-corrupting

**User Story:** As a Training_Coordinator, I want scenario activation and teardown to be reversible and non-destructive to long-term state, so that I can run training back-to-back without rebuilding the demo environment.

#### Acceptance Criteria

1. WHEN the Teardown_Procedure for any scenario completes, THE astronomy-db PostgreSQL volume SHALL contain the same set of rows in the `catalog.products` table as it did before activation.
2. WHEN the Teardown_Procedure for any scenario completes, THE OpenSearch `otel-logs-*` indexes SHALL NOT have been deleted or rotated as part of the teardown.
3. WHEN a scenario is activated while a different scenario is already active, THE Scenario_Controller SHALL refuse the second activation AND SHALL exit non-zero with an error naming the currently-active scenario.
4. WHEN the Teardown_Procedure is invoked while no scenario is active, THE Scenario_Controller SHALL produce a non-error success outcome AND SHALL exit with status zero.
5. WHEN activation is performed twice back-to-back for the same scenario, the observable telemetry state after the second activation SHALL match the state after the first (idempotence).
6. WHEN teardown is performed twice back-to-back for the same scenario, the observable telemetry state after the second teardown SHALL match the state after the first (idempotence).
7. WHERE Kafka, accounting, and fraud-detection services are uncommented in `docker-compose.minimal.yml` by the Training_Coordinator, THE Teardown_Procedure SHALL NOT reset Kafka consumer-group offsets; under the default minimal compose these services are not present and this acceptance criterion is vacuously satisfied.

### Requirement 12: Scenarios coexist with existing demo feature flags and alerts

**User Story:** As a Training_Coordinator, I want the training scenarios to add new feature flags and alerts without conflicting with the existing demo's fault-injection flags and alert rules, so that the demo's own showcase behaviors remain available.

#### Acceptance Criteria

1. THE new feature flags `quoteSilentCorruption` and `productReviewsMemoryLeak` SHALL be added to `src/flagd/demo.flagd.json` with `state: ENABLED` and `defaultVariant: off`, AND SHALL be additive (no removal of existing flags).
2. THE new Prometheus alerts `AnomalousZeroValueOrders`, `PaymentServiceUnreachable`, and `ProductReviewsMemoryHigh` SHALL be added to `src/prometheus/alert-rules.yml` without removing or modifying any alert rule other than the replacement of `SomethingWrongHere` stipulated in Requirement 6.10.
3. WHILE the baseline demo's existing fault-injection flags (`paymentFailure`, `paymentUnreachable`, `cartFailure`, `productCatalogFailure`, `kafkaQueueProblems`, `adFailure`, `adHighCpu`, `adManualGc`, `emailMemoryLeak`, `recommendationCacheFailure`, `failedReadinessProbe`, `loadGeneratorFloodHomepage`, `imageSlowLoad`, `llmInaccurateResponse`, `llmRateLimitError`) are at `defaultVariant: off` AND no training scenario is active, THE three new Scenario_Specific_Alerts SHALL NOT fire; note that `paymentUnreachable` currently defaults to `on` in `src/flagd/demo.flagd.json` and THE Baseline definition SHALL therefore require a one-time edit to set it to `off` before baseline measurements are taken.
4. WHEN a training scenario is active, THE existing demo fault-injection flags SHALL remain toggleable via `flagd-ui` by the Training_Coordinator.
5. IF the Training_Coordinator activates a training scenario while the existing `paymentFailure` flag is set to a non-zero variant, THEN THE Scenario_Controller SHALL log a warning naming both flags AND SHALL proceed with activation (no hard failure).

### Requirement 13: Execution time budgets are measured and reported

**User Story:** As a Training_Coordinator, I want the feature to record and report the wall-clock time each SRE_Trainee takes to reach root cause for Case_1 and Case_2, and to confirm Case_3 remains unsolved within its budget, so that I can calibrate training difficulty over time.

#### Acceptance Criteria

1. THE Scenario_Controller SHALL record the wall-clock timestamp at which each scenario is activated AND the wall-clock timestamp at which the Training_Coordinator marks the scenario as `solved` or `timed-out`.
2. THE feature deliverable SHALL document the expected time-to-solve budgets: Case_1 between 45 and 90 minutes inclusive, Case_2 strictly less than 15 minutes, Case_3 with no upper bound because it is intentionally unsolvable from telemetry alone.
3. WHERE a Training_Coordinator marks Case_1 as `solved` in under 15 minutes, THE Scenario_Controller SHALL emit a warning that the scenario may have been leaked or the trainee may have prior knowledge.
4. WHERE a Training_Coordinator marks Case_3 as `solved` via telemetry alone, THE Scenario_Controller SHALL emit an error that Case_3 is designed to be telemetry-unsolvable AND SHALL request the trainee document the out-of-band information used.
