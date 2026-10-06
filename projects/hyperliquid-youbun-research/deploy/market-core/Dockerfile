FROM python:3.11-slim
WORKDIR /app
COPY projects/hyperliquid-youbun-research/deploy/market-core/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY . /app
ENTRYPOINT ["python", "projects/hyperliquid-youbun-research/scripts/forward_market_core_live.py", "--output-root", "/data/forward-market-core-v1", "--include-trades"]
