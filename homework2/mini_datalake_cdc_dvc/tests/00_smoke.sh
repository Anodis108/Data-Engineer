# run
# chmod +x tests/00_smoke.sh
# ./tests/00_smoke.sh


#!/usr/bin/env bash
set -euo pipefail

echo "== docker ps =="
docker ps --format "table {{.Names}}\t{{.Status}}" | sed -n '1,200p'

echo "== Health endpoints =="
echo "- MinIO health:"
curl -sf http://localhost:9000/minio/health/live >/dev/null && echo "  OK"

echo "- Trino /v1/info:"
curl -sf http://localhost:8080/v1/info | head -c 200; echo
echo "  OK"

echo "- Kafka UI:"
curl -sf http://localhost:8081 >/dev/null && echo "  OK"

echo "- Connect:"
curl -sf http://localhost:8083/ | head -c 120; echo
echo "  OK"

echo "- RabbitMQ mgmt:"
curl -sf http://localhost:15672 >/dev/null && echo "  OK"

echo "✅ Smoke ok"
