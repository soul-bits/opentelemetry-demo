# SRE Debug Challenge Scenarios

Fault-injection training scenarios for the OpenTelemetry Demo stack (`docker-compose.minimal.yml`). Used to teach SRE and QA engineers Root Cause Analysis (RCA) using Metrics, Logs, and Traces.

## Setup

### Prerequisites
- Python 3.8+
- `docker-compose` (minimal stack running at `localhost`)
- `promtool` (Prometheus CLI tool)

### Installation

Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r scenarios/requirements.txt
```

## Testing

### Unit Tests (No Live Stack Required)

Test the scenario modules without a running stack:

```bash
# Activate venv if not already active
source .venv/bin/activate

# Test module imports
python3 << 'EOF'
from scenarios import state_file, flagd_client, prometheus_client, opensearch_client, jaeger_client
print("✅ All modules import successfully")
EOF
```

### CLI Tests (No Live Stack Required)

Test the CLI interface:

```bash
# Show help
python -m scenarios.scenarios --help

# Test subcommands
python -m scenarios.scenarios activate --help
python -m scenarios.scenarios verify --help
python -m scenarios.scenarios teardown --help
python -m scenarios.scenarios status --help
python -m scenarios.scenarios solve --help

# Test that stubs raise NotImplementedError (expected at this stage)
python -m scenarios.scenarios activate case1 2>&1
# Expected output: "scenarios: not implemented: activate('case1') is not implemented yet (pending task 3.1)"
```

### Integration Tests (Live Stack Required)

Once the controller and scenarios are fully implemented:

```bash
# 1. Start the minimal stack
docker compose -f docker-compose.minimal.yml up -d

# 2. Wait for Prometheus, Grafana, Jaeger, OpenSearch to be ready
sleep 30

# 3. Activate a scenario
python -m scenarios.scenarios activate case1

# 4. Verify alert fires
python -m scenarios.scenarios verify case1

# 5. Tear down
python -m scenarios.scenarios teardown case1

# 6. Run property-based tests
INTEGRATION=1 pytest scenarios/tests/test_properties.py -m integration -v
```

## Project Structure

```
scenarios/
├── README.md                    (this file)
├── requirements.txt             (Python dependencies)
├── __init__.py                  (package init)
├── scenarios.py                 (CLI entry point)
├── controller.py                (state machine: activate/verify/teardown/status/solve)
├── state_file.py                (atomic state persistence with POSIX locks)
├── flagd_client.py              (atomic read/write of flagd config)
├── prometheus_client.py         (reload, query, validate alert rules)
├── opensearch_client.py         (count, search logs)
├── jaeger_client.py             (find, fetch traces)
├── validator.py                 (service-map observability validator)
└── tests/
    ├── __init__.py
    ├── test_properties.py        (property-based tests with Hypothesis)
    ├── test_alert_text.py        (alert text compliance)
    ├── test_rules_file.py        (rules file validity)
    └── test_tm_a_compliance.py   (threat model compliance)
```

## Task Status

See `sre-debug-challenge-scenarios/tasks.md` for current implementation status.

| Task | Status |
|------|--------|
| Task 1: CLI scaffold | ✅ TESTED |
| Task 2: Client modules | ✅ TESTED |
| Task 3: Controller state machine | ⏳ Pending |
| Task 4: Observability validator | ⏳ Pending |
| Task 5: Case 2 (EASY) | ⏳ Pending |
| Task 6: Case 1 (HARD) | ⏳ Pending |
| Task 7: Case 3 (IMPOSSIBLE) | ⏳ Pending |
| Tasks 8-9: Tests | ⏳ Pending |
| Task 10-12: E2E & final tests | ⏳ Pending |
