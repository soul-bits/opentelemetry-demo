```mermaid
graph LR

  %% User & Traffic
  subgraph "User Traffic"
    user["User (Browser)"]
    loadgen["Load Generator (Locust)"]
    frontend_proxy["Frontend Proxy (Envoy)"]
    frontend["Frontend (Next.js Web UI)"]
  end

  loadgen -->|synthetic HTTP load| frontend_proxy
  user -->|browses shop / places orders| frontend_proxy
  frontend_proxy -->|routes HTTP to app| frontend

  %% Core Business Services
  subgraph "Core Business Services"
    cart["Cart (C# gRPC)"]
    checkout["Checkout (Go gRPC)"]
    product_catalog["Product Catalog (Go gRPC)"]
    recommendation["Recommendation (Python gRPC)"]
    currency["Currency (C++ gRPC)"]
    shipping["Shipping (Rust HTTP)"]
    quote["Quote (Rust HTTP)"]
    flagd["flagd (Feature Flags)"]
  end

  %% Data Stores
  subgraph "Data Stores"
    valkey_cart["Valkey (Cart key-value store)"]
    astronomy_db["Astronomy DB (PostgreSQL)"]
  end

  %% Observability Stack
  subgraph "Telemetry & Observability"
    otel_collector["OTel Collector"]
    prometheus["Prometheus (metrics + alert rules)"]
    alertmanager["Alertmanager (alert routing)"]
    alert_webhook["Alert Webhook Server (RCA agent hook)"]
    jaeger["Jaeger (trace storage & UI)"]
    opensearch["OpenSearch (log storage)"]
    grafana["Grafana (dashboards)"]
  end

  %% Frontend -> Backend interactions
  frontend -->|AddItem / GetCart| cart
  frontend -->|PlaceOrder| checkout
  frontend -->|GetProduct / ListProducts| product_catalog
  frontend -->|ListRecommendations| recommendation
  frontend -->|price display / currency selection| currency
  frontend -->|shipping info for UI| shipping

  %% Checkout interactions
  checkout -->|GetCart / EmptyCart - read & clear cart| cart
  checkout -->|GetProduct - per-item product details| product_catalog
  checkout -->|Convert - order totals to user currency| currency
  checkout -->|/get-quote, /ship-order - shipping quote & fulfillment| shipping

  %% Cart internals
  cart -->|read/write cart items| valkey_cart
  cart -->|cartFailure flag| flagd

  %% Product Catalog internals
  product_catalog -->|query catalog.products table| astronomy_db
  product_catalog -->|productCatalogFailure flag| flagd

  %% Recommendation service
  recommendation -->|ListProducts / GetProduct - source product IDs| product_catalog
  recommendation -->|recommendationCacheFailure flag| flagd

  %% Shipping & Quote
  shipping -->|/get-quote - compute shipping cost| quote

  %% Feature flags fan-out
  frontend -->|evaluate UI flags| flagd
  checkout -->|paymentUnreachable flag| flagd

  %% Telemetry flow
  frontend -->|OTLP traces/metrics/logs| otel_collector
  cart -->|OTLP traces/metrics/logs| otel_collector
  checkout -->|OTLP traces/metrics/logs| otel_collector
  product_catalog -->|OTLP traces/metrics/logs| otel_collector
  recommendation -->|OTLP traces/metrics/logs| otel_collector
  currency -->|OTLP traces/metrics/logs| otel_collector
  shipping -->|OTLP traces/metrics/logs| otel_collector
  quote -->|OTLP traces/metrics/logs| otel_collector

  otel_collector -->|export metrics| prometheus
  otel_collector -->|export traces| jaeger
  otel_collector -->|export logs| opensearch

  prometheus -->|evaluate alert rules| alertmanager
  alertmanager -->|HTTP webhook| alert_webhook

  grafana -->|query metrics| prometheus
  grafana -->|query traces| jaeger
  grafana -->|query logs| opensearch

  frontend_proxy -->|expose Grafana/Jaeger UIs| grafana
  frontend_proxy -->|expose Grafana/Jaeger UIs| jaeger
```

---

## Frontend & Business Services (no observability)

```mermaid
graph LR

  frontend["Frontend (Next.js Web UI)"]

  subgraph "Business Services"
    cart["Cart (C# gRPC)"]
    checkout["Checkout (Go gRPC)"]
    product_catalog["Product Catalog (Go gRPC)"]
    recommendation["Recommendation (Python gRPC)"]
    currency["Currency (C++ gRPC)"]
    shipping["Shipping (Rust HTTP)"]
    quote["Quote (Rust HTTP)"]
    flagd["flagd (Feature Flags)"]
  end

  subgraph "Data Stores"
    valkey_cart["Valkey (Cart key-value store)"]
    astronomy_db["Astronomy DB (PostgreSQL)"]
  end

  frontend -->|AddItem / GetCart| cart
  frontend -->|PlaceOrder| checkout
  frontend -->|GetProduct / ListProducts| product_catalog
  frontend -->|ListRecommendations| recommendation
  frontend -->|currency selection| currency
  frontend -->|shipping info| shipping
  frontend -->|evaluate UI flags| flagd

  checkout -->|GetCart / EmptyCart - read & clear cart| cart
  checkout -->|GetProduct - per-item product details| product_catalog
  checkout -->|Convert - order totals to user currency| currency
  checkout -->|/get-quote, /ship-order - shipping quote & fulfillment| shipping
  checkout -->|paymentUnreachable flag| flagd

  cart -->|read/write cart items| valkey_cart
  cart -->|cartFailure flag| flagd

  product_catalog -->|query catalog.products table| astronomy_db
  product_catalog -->|productCatalogFailure flag| flagd

  recommendation -->|ListProducts / GetProduct - source product IDs| product_catalog
  recommendation -->|recommendationCacheFailure flag| flagd

  shipping -->|/get-quote - compute shipping cost| quote
```

---

## Checkout Flow (order placement detail)

```mermaid
graph LR

  frontend["Frontend (Next.js Web UI)"]
  checkout["Checkout (Go gRPC)"]
  cart["Cart (C# gRPC)"]
  product_catalog["Product Catalog (Go gRPC)"]
  currency["Currency (C++ gRPC)"]
  shipping["Shipping (Rust HTTP)"]
  quote["Quote (Rust HTTP)"]
  valkey_cart["Valkey (Cart key-value store)"]
  astronomy_db["Astronomy DB (PostgreSQL)"]
  flagd["flagd (Feature Flags)"]

  frontend -->|PlaceOrder| checkout

  checkout -->|GetCart - fetch items in cart| cart
  checkout -->|GetProduct - look up price & details per item| product_catalog
  checkout -->|Convert - convert order total to user currency| currency
  checkout -->|/get-quote - request shipping cost estimate| shipping
  checkout -->|/ship-order - trigger fulfillment| shipping
  checkout -->|EmptyCart - clear cart after payment| cart
  checkout -->|paymentUnreachable flag| flagd

  cart -->|read/write cart state| valkey_cart
  cart -->|cartFailure flag| flagd

  product_catalog -->|query catalog.products| astronomy_db
  product_catalog -->|productCatalogFailure flag| flagd

  shipping -->|/get-quote - compute cost from quote service| quote
```

---

## Business Services Only (no flagd, no observability)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
  'primaryColor': '#1a7a73',
  'primaryTextColor': '#f0fdfa',
  'primaryBorderColor': '#2dd4bf',
  'lineColor': '#5eead4',
  'secondaryColor': '#0d4a45',
  'tertiaryColor': '#0f3d39',
  'clusterBkg': '#0d4a45',
  'clusterBorder': '#2dd4bf',
  'titleColor': '#f0fdfa',
  'background': 'transparent',
  'edgeLabelBackground': 'transparent',
  'fontFamily': 'monospace',
  'fontSize': '25px'
}}}%%
graph TB

  frontend["Frontend (Next.js Web UI)"]

  subgraph cartCluster[" "]
    cart["Cart (C# gRPC)"]
    valkey_cart["Valkey (key-value store)"]
  end

  subgraph checkoutCluster[" "]
    checkout["Checkout (Go gRPC)"]
    payment["Payment (Go gRPC)"]
  end

  subgraph catalogCluster[" "]
    product_catalog["Product Catalog (Go gRPC)"]
    recommendation["Recommendation (Python gRPC)"]
    astronomy_db["Astronomy DB (PostgreSQL)"]
  end

  subgraph pricingCluster[" "]
    currency["Currency (C++ gRPC)"]
    shipping["Shipping (Rust HTTP)"]
    quote["Quote (Rust HTTP)"]
  end

  frontend -->|GetCart / AddItem| cart
  frontend -->|PlaceOrder| checkout
  frontend -->|GetProduct| product_catalog
  frontend -->|ListRecommendations| recommendation
  frontend -->|GetCurrencies| currency
  frontend -->|GetShippingCost| shipping

  checkout -->|GetCart / EmptyCart| cart
  checkout -->|GetProduct| product_catalog
  checkout -->|Convert| currency
  checkout -->|Quote + Ship| shipping
  checkout -->|Charge| payment

  cart -->|read / write| valkey_cart
  product_catalog -->|SQL query| astronomy_db
  recommendation -->|GetProduct IDs| product_catalog
  shipping -->|get-quote| quote

  linkStyle default stroke:#5eead4,color:#99f6e4
```

---

## Alert: OperationalAnomalyDetected — paymentUnreachable

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
  'primaryColor': '#1a7a73',
  'primaryTextColor': '#f0fdfa',
  'primaryBorderColor': '#2dd4bf',
  'lineColor': '#5eead4',
  'secondaryColor': '#0d4a45',
  'tertiaryColor': '#0f3d39',
  'clusterBkg': '#0d4a45',
  'clusterBorder': '#2dd4bf',
  'titleColor': '#f0fdfa',
  'background': 'transparent',
  'edgeLabelBackground': 'transparent',
  'fontFamily': 'monospace',
  'fontSize': '25px'
}}}%%
graph TB

  frontend["Frontend (Next.js Web UI)"]

  subgraph cartCluster[" "]
    cart["Cart (C# gRPC)"]
    valkey_cart["Valkey (key-value store)"]
  end

  subgraph checkoutCluster[" "]
    checkout["⚠️ Checkout (Go gRPC)"]:::alertNode
    payment["Payment (Go gRPC)"]:::broken
  end

  subgraph catalogCluster[" "]
    product_catalog["Product Catalog (Go gRPC)"]
    recommendation["Recommendation (Python gRPC)"]
    astronomy_db["Astronomy DB (PostgreSQL)"]
  end

  subgraph pricingCluster[" "]
    currency["Currency (C++ gRPC)"]
    shipping["Shipping (Rust HTTP)"]
    quote["Quote (Rust HTTP)"]
  end

  frontend -->|GetCart / AddItem| cart
  frontend -->|PlaceOrder| checkout
  frontend -->|GetProduct| product_catalog
  frontend -->|ListRecommendations| recommendation
  frontend -->|GetCurrencies| currency
  frontend -->|GetShippingCost| shipping

  checkout -->|GetCart / EmptyCart| cart
  checkout -->|GetProduct| product_catalog
  checkout -->|Convert| currency
  checkout -->|Quote + Ship| shipping
  checkout -. Charge - UNAVAILABLE .-> payment

  cart -->|read / write| valkey_cart
  product_catalog -->|SQL query| astronomy_db
  recommendation -->|GetProduct IDs| product_catalog
  shipping -->|get-quote| quote

  classDef broken fill:#dc2626,stroke:#ef4444,color:#fff
  classDef alertNode fill:#f59e0b,stroke:#fbbf24,color:#000

  linkStyle default stroke:#5eead4,color:#99f6e4
  linkStyle 10 stroke:#ef4444,color:#fca5a5
```
