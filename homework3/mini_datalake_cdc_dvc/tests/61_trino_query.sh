# run
# chmod +x tests/61_trino_query.sh
# ./tests/61_trino_query.sh


#!/usr/bin/env bash
#!/usr/bin/env bash
set -euo pipefail

TRINO_URL="http://localhost:8080"
CATALOG="hive"
SCHEMA="raw"

echo "== Run DDL =="
docker exec -i trino-coordinator trino \
  --server http://localhost:8080 \
  --catalog hive \
  --schema raw < tests/60_trino_ddl.sql

echo "✅ DDL ok"

echo "== Query sample =="

QUERY="SELECT * FROM hive.raw.vision_events LIMIT 10"

# gửi query lần đầu
RESP=$(curl -s -X POST \
  -H "X-Trino-User: test" \
  --data "$QUERY" \
  "$TRINO_URL/v1/statement")

echo "$RESP"

# lấy nextUri bằng sed (không jq)
NEXT_URI=$(echo "$RESP" | sed -n 's/.*"nextUri":"\([^"]*\)".*/\1/p')

# poll cho đến khi có data
while [[ -n "$NEXT_URI" ]]; do
  RESP=$(curl -s "$NEXT_URI")
  echo "$RESP"
  NEXT_URI=$(echo "$RESP" | sed -n 's/.*"nextUri":"\([^"]*\)".*/\1/p')
done



