FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake ninja-build && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/kraken
COPY pyproject.toml CMakeLists.txt README.md /opt/kraken/
COPY cpp /opt/kraken/cpp
COPY vendor_plugins /opt/kraken/vendor_plugins
COPY src /opt/kraken/src
COPY tools /opt/kraken/tools
RUN python -m pip install --no-cache-dir . && useradd --create-home --uid 10001 kraken
USER kraken
ENV KRAKEN_OPS_HOST=0.0.0.0
ENV KRAKEN_STORE_PATH=/var/lib/kraken/observations.db
ENV KRAKEN_ALERT_PATH=/var/lib/kraken/alerts.jsonl
ENV KRAKEN_KILL_SWITCH_PATH=/var/lib/kraken/kill-switch.json
ENV KRAKEN_RISK_STATE_PATH=/var/lib/kraken/risk-state.json
ENV KRAKEN_EXECUTION_AUDIT_PATH=/var/lib/kraken/execution.jsonl
VOLUME ["/var/lib/kraken"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
ENTRYPOINT ["python", "tools/run_production.py"]
