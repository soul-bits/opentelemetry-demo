<!-- markdownlint-disable-next-line -->
# <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" alt="OTel logo" width="45"> OpenTelemetry Demo — RCA Testing Stack

> **This is a trimmed fork** of the [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) used as a live environment for **SRE Root Cause Analysis (RCA) testing**. Three fault-injection scenarios fire Prometheus alerts of varying difficulty; trainees debug them using only Metrics, Logs, and Traces.

---

## Stack Overview

An astronomy-themed e-commerce shop built from ~15 microservices in 8 languages. All services export telemetry via OTLP to a central OpenTelemetry Collector, which fans out to three backends:

```
┌─────────────────────────────────────────────────────────────────┐
│                        LOAD GENERATOR (Locust)                  │
│                              :8089                              │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND-PROXY (Envoy) :80                  │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND (Next.js) :8080                  │
└───┬────────┬────────┬────────┬────────┬────────┬────────┬───────┘
    ▼        ▼        ▼        ▼        ▼        ▼        ▼
  cart    checkout  currency shipping recommend  product   product
  (.NET)   (Go)     (C++)   (Rust)   (Python)  -catalog  -reviews
  :7070    :5050    :7001   :50050   :9001     (Go)      (Python)
    │        │                 │        │      :3550      :3551
    ▼        │                 ▼        ▼        │          │
 valkey      │               quote    flagd   astronomy   astronomy
 (Redis)     │               (PHP)    :8013     -db         -db
 :6379       │               :8090              (Postgres)  (Postgres)
             │                                  :5432       :5432
             ▼
          payment
          (Node.js)
          :50051
```

### Telemetry Pipeline

```
All Services ──OTLP──► OTel Collector (:4317 gRPC, :4318 HTTP)
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
            Jaeger       Prometheus     OpenSearch
           (traces)      (metrics)       (logs)
           :16686         :9090          :9200
                ▲             ▲             ▲
                └─────────────┼─────────────┘
                              │
                           Grafana :3000
```

### Key Ports

| Port | Service | What you use it for |
|------|---------|---------------------|
| 80 | frontend-proxy | Browse the shop |
| 3000 | Grafana | Dashboards, explore metrics/logs/traces |
| 8089 | Locust | Load generator control |
| 9090 | Prometheus | PromQL queries, alert status |
| 9093 | Alertmanager | Alert routing and silencing |
| 16686 | Jaeger | Distributed trace search |
| 9200 | OpenSearch | Log search (via Grafana datasource) |

### Active Services (docker-compose.minimal.yml)

| Service | Language | Protocol | Role |
|---------|----------|----------|------|
| frontend | TypeScript | HTTP | Web UI, SSR |
| frontend-proxy | Envoy | HTTP | Reverse proxy |
| checkout | Go | gRPC | Order orchestration |
| payment | Node.js | gRPC | Credit card charges |
| cart | .NET | gRPC | Shopping cart (backed by Valkey) |
| product-catalog | Go | gRPC | Product listing (backed by PostgreSQL) |
| product-reviews | Python | gRPC | Product reviews |
| currency | C++ | gRPC | Currency conversion |
| shipping | Rust | HTTP | Shipping quotes (calls quote service) |
| quote | PHP | HTTP | Shipping cost calculation |
| recommendation | Python | gRPC | Product recommendations |
| flagd | Go | gRPC | Feature flags (OpenFeature) |
| load-generator | Python | HTTP | Synthetic traffic (Locust) |

### Disabled Services (commented out in minimal compose)

`ad`, `email`, `image-provider`, `flagd-ui`, `llm`, `kafka`, `accounting`, `fraud-detection`

### Fault Injection via Feature Flags

Edit `src/flagd/demo.flagd.json` — flagd hot-reloads on file change, no restart needed.

| Flag | Effect |
|------|--------|
| `paymentUnreachable` | Checkout dials wrong payment address → gRPC UNAVAILABLE |
| `cartFailure` | Cart service returns errors |
| `productCatalogFailure` | Product catalog errors on one product |
| `recommendationCacheFailure` | Recommendation cache misses |
| `paymentFailure` | Payment fails at configurable % |

### SRE Training Scenarios (this fork's addition)

Three scenarios activated via `python -m scenarios.scenarios activate {case1|case2|case3}`:

| Case | Difficulty | Alert | What breaks | Expected RCA outcome |
|------|-----------|-------|-------------|---------------------|
| 1 | HARD | `AnomalousZeroValueOrders` | PHP quote silently returns $0 | Trainee walks trace 4 hops deep to find swallowed exception |
| 2 | EASY | `PaymentServiceUnreachable` | Checkout dials `badAddress:50051` | Trainee follows alert text → Jaeger → done in 15 min |
| 3 | IMPOSSIBLE | `ProductReviewsMemoryHigh` | Background thread leaks memory | Trainee exhausts all signals, escalates with specific ask |

See `.kiro/specs/sre-debug-challenge-scenarios/golden-dataset.md` for the full grading rubric.

---

## Quick Start

```bash
# Start the minimal stack
docker compose -f docker-compose.minimal.yml up -d

# Wait for services to stabilize (~2 min), then verify
curl -s http://localhost:9090/-/healthy   # Prometheus
curl -s http://localhost:16686/           # Jaeger UI
curl -s http://localhost:3000/api/health  # Grafana

# Open the shop
open http://localhost

# Open the load generator
open http://localhost:8089
```

---

## Upstream Documentation

[![Slack](https://img.shields.io/badge/slack-@cncf/otel/demo-brightgreen.svg?logo=slack)](https://cloud-native.slack.com/archives/C03B4CWV4DA)
[![Version](https://img.shields.io/github/v/release/open-telemetry/opentelemetry-demo?color=blueviolet)](https://github.com/open-telemetry/opentelemetry-demo/releases)
[![Commits](https://img.shields.io/github/commits-since/open-telemetry/opentelemetry-demo/latest?color=ff69b4&include_prereleases)](https://github.com/open-telemetry/opentelemetry-demo/graphs/commit-activity)
[![Downloads](https://img.shields.io/docker/pulls/otel/demo)](https://hub.docker.com/r/otel/demo)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?color=red)](https://github.com/open-telemetry/opentelemetry-demo/blob/main/LICENSE)
[![Integration Tests](https://github.com/open-telemetry/opentelemetry-demo/actions/workflows/run-integration-tests.yml/badge.svg)](https://github.com/open-telemetry/opentelemetry-demo/actions/workflows/run-integration-tests.yml)
[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/opentelemetry-demo)](https://artifacthub.io/packages/helm/opentelemetry-helm/opentelemetry-demo)
[![FOSSA Status](https://app.fossa.com/api/projects/custom%2B162%2Fgithub.com%2Fopen-telemetry%2Fopentelemetry-demo.svg?type=shield&issueType=license)](https://app.fossa.com/projects/custom%2B162%2Fgithub.com%2Fopen-telemetry%2Fopentelemetry-demo?ref=badge_shield&issueType=license)
[![FOSSA Status](https://app.fossa.com/api/projects/custom%2B162%2Fgithub.com%2Fopen-telemetry%2Fopentelemetry-demo.svg?type=shield&issueType=security)](https://app.fossa.com/projects/custom%2B162%2Fgithub.com%2Fopen-telemetry%2Fopentelemetry-demo?ref=badge_shield&issueType=security)
[![OpenSSF Scorecard for opentelemetry-demo](https://api.scorecard.dev/projects/github.com/open-telemetry/opentelemetry-demo/badge)](https://scorecard.dev/viewer/?uri=github.com/open-telemetry/opentelemetry-demo)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/9247/badge)](https://www.bestpractices.dev/en/projects/9247)

## Welcome to the OpenTelemetry Astronomy Shop Demo

This repository contains the OpenTelemetry Astronomy Shop, a microservice-based
distributed system intended to illustrate the implementation of OpenTelemetry in
a near real-world environment.

Our goals are threefold:

- Provide a realistic example of a distributed system that can be used to
  demonstrate OpenTelemetry instrumentation and observability.
- Build a base for vendors, tooling authors, and others to extend and
  demonstrate their OpenTelemetry integrations.
- Create a living example for OpenTelemetry contributors to use for testing new
  versions of the API, SDK, and other components or enhancements.

We've already made [huge
progress](https://github.com/open-telemetry/opentelemetry-demo/blob/main/CHANGELOG.md),
and development is ongoing. We hope to represent the full feature set of
OpenTelemetry across its languages in the future.

If you'd like to help (**which we would love**), check out our [contributing
guidance](./CONTRIBUTING.md).

If you'd like to extend this demo or maintain a fork of it, read our
[fork guidance](https://opentelemetry.io/docs/demo/forking/).

## Quick start

You can be up and running with the demo in a few minutes. Check out the docs for
your preferred deployment method:

- [Docker](https://opentelemetry.io/docs/demo/docker_deployment/)
- [Kubernetes](https://opentelemetry.io/docs/demo/kubernetes_deployment/)

## Documentation

For detailed documentation, see [Demo Documentation][docs]. If you're curious
about a specific feature, the [docs landing page][docs] can point you in the
right direction.

## Demos featuring the Astronomy Shop

We welcome any vendor to fork the project to demonstrate their services and
adding a link below. The community is committed to maintaining the project and
keeping it up to date for you.

|                           |                |                                  |
|---------------------------|----------------|----------------------------------|
| [AlibabaCloud LogService] | [Grafana Labs] | [Sentry]                         |
| [Apache Doris]            | [Guance]       | [ServiceNow Cloud Observability] |
| [AppDynamics]             | [Honeycomb.io] | [SigNoz]                         |
| [Aspecto]                 | [Instana]      | [SolarWinds Observability]       |
| [Axiom]                   | [Kloudfuse]    | [Splunk]                         |
| [Axoflow]                 | [Kopai]        | [Sumo Logic]                     |
| [Azure Data Explorer]     | [Last9]        | [TelemetryHub]                   |
| [Causely]                 | [Liatrio]      | [Teletrace]                      |
| [ClickStack]              | [Logz.io]      | [Tinybird]                       |
| [Coralogix]               | [New Relic]    | [Tracetest]                      |
| [Dash0]                   | [Oodle]        | [Tsuga]                          |
| [Datadog]                 | [OpenObserve]  | [Uptrace]                        |
| [Dynatrace]               | [OpenSearch]   | [VictoriaMetrics]                |
| [Elastic]                 | [Oracle]       |                                  |
| [Google Cloud]            | [Parseable]    |                                  |

## Contributing

To get involved with the project see our [CONTRIBUTING](CONTRIBUTING.md)
documentation. Our [SIG Calls](CONTRIBUTING.md#join-a-sig-call) are every other
Wednesday at 8:30 AM PST and anyone is welcome.

### Maintainers

- [Cyrille Le Clerc](https://github.com/cyrille-leclerc), Grafana Labs
- [Juliano Costa](https://github.com/julianocosta89), Datadog
- [Pierre Tessier](https://github.com/puckpuck), Honeycomb
- [Roger Coll](https://github.com/rogercoll), Elastic

For more information about the maintainer role, see the [community repository](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#maintainer).

### Approvers

- [Cedric Ziel](https://github.com/cedricziel), Grafana Labs
- [Mikko Viitanen](https://github.com/mviitane), Dynatrace
- [Piotr Kie&#x142;kowicz](https://github.com/Kielek), Splunk
- [Shenoy Pratik](https://github.com/ps48), AWS OpenSearch

For more information about the approver role, see the [community repository](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#approver).

### Emeritus

- [Austin Parker](https://github.com/austinlparker)
- [Carter Socha](https://github.com/cartersocha)
- [Michael Maxwell](https://github.com/mic-max)
- [Morgan McLean](https://github.com/mtwo)
- [Penghan Wang](https://github.com/wph95)
- [Reiley Yang](https://github.com/reyang)
- [Ziqi Zhao](https://github.com/fatsheep9146)

For more information about the emeritus role, see the [community repository](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#emeritus-maintainerapprovertriager).

### Thanks to all the people who have contributed

[![contributors](https://contributors-img.web.app/image?repo=open-telemetry/opentelemetry-demo)](https://github.com/open-telemetry/opentelemetry-demo/graphs/contributors)

[docs]: https://opentelemetry.io/docs/demo/

<!-- Links for Demos featuring the Astronomy Shop section -->

[AlibabaCloud LogService]: https://github.com/aliyun-sls/opentelemetry-demo
[AppDynamics]: https://community.splunk.com/t5/AppDynamics-Knowledge-Base/How-to-observe-Kubernetes-deployment-of-OpenTelemetry-demo-app/ta-p/741454
[Apache Doris]: https://github.com/apache/doris-opentelemetry-demo
[Aspecto]: https://github.com/aspecto-io/opentelemetry-demo
[Axiom]: https://play.axiom.co/axiom-play-qf1k/dashboards/otel.traces.otel-demo-traces
[Axoflow]: https://axoflow.com/opentelemetry-support-in-more-detail-in-axosyslog-and-syslog-ng/
[Azure Data Explorer]: https://github.com/Azure/Azure-kusto-opentelemetry-demo
[Causely]: https://github.com/causely-oss/otel-demo
[ClickStack]: https://github.com/ClickHouse/opentelemetry-demo
[Coralogix]: https://coralogix.com/blog/configure-otel-demo-send-telemetry-data-coralogix
[Dash0]: https://github.com/dash0hq/opentelemetry-demo
[Datadog]: https://docs.datadoghq.com/opentelemetry/guide/otel_demo_to_datadog
[Dynatrace]: https://www.dynatrace.com/news/blog/opentelemetry-demo-application-with-dynatrace/
[Elastic]: https://github.com/elastic/opentelemetry-demo
[Google Cloud]: https://github.com/GoogleCloudPlatform/opentelemetry-demo
[Grafana Labs]: https://github.com/grafana/opentelemetry-demo
[Guance]: https://github.com/GuanceCloud/opentelemetry-demo
[Honeycomb.io]: https://github.com/honeycombio/opentelemetry-demo
[Instana]: https://github.com/instana/opentelemetry-demo
[Kloudfuse]: https://github.com/kloudfuse/opentelemetry-demo
[Kopai]: https://github.com/kopai-app/opentelemetry-demo/tree/main/kopai
[Last9]: https://last9.io/docs/integrations-opentelemetry-demo/
[Liatrio]: https://github.com/liatrio/opentelemetry-demo
[Logz.io]: https://logz.io/learn/how-to-run-opentelemetry-demo-with-logz-io/
[New Relic]: https://github.com/newrelic/opentelemetry-demo
[Oodle]: https://blog.oodle.ai/meet-oodle-unified-and-ai-native-observability/
[OpenSearch]: https://github.com/opensearch-project/opentelemetry-demo
[OpenObserve]: https://openobserve.ai/blog/opentelemetry-astronomy-shop-demo/
[Oracle]: https://github.com/oracle-quickstart/oci-o11y-solutions/blob/main/knowledge-content/opentelemetry-demo
[Parseable]: https://www.parseable.com/blog/open-telemetry-demo-with-parseable-a-complete-observability-setup
[Sentry]: https://github.com/getsentry/opentelemetry-demo
[ServiceNow Cloud Observability]: https://docs.lightstep.com/otel/quick-start-operator#send-data-from-the-opentelemetry-demo
[SigNoz]: https://signoz.io/blog/opentelemetry-demo/
[SolarWinds Observability]: https://github.com/solarwinds/opentelemetry-demo
[Splunk]: https://github.com/signalfx/opentelemetry-demo
[Sumo Logic]: https://www.sumologic.com/blog/common-opentelemetry-demo-application/
[TelemetryHub]: https://github.com/TelemetryHub/opentelemetry-demo/tree/telemetryhub-backend
[Teletrace]: https://github.com/teletrace/opentelemetry-demo
[Tinybird]: https://github.com/tinybirdco/opentelemetry-demo
[Tracetest]: https://github.com/kubeshop/opentelemetry-demo
[Tsuga]: https://github.com/tsuga-dev/opentelemetry-demo
[Uptrace]: https://github.com/uptrace/uptrace/tree/master/example/opentelemetry-demo
[VictoriaMetrics]: https://github.com/VictoriaMetrics-Community/opentelemetry-demo
