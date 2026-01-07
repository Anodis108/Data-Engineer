# run
# chmod +x tests/11_test_postgres_cdc.sh
# ./tests/11_test_postgres_cdc.sh


#!/usr/bin/env bash
#!/usr/bin/env bash
set -euo pipefail

echo "== Check Debezium connector list =="
curl -sf http://localhost:8083/connectors | cat
echo

echo "== Run CDC mutations on cdc-postgres =="
docker exec -i cdc-postgres psql -U dbz -d inventory < tests/10_postgres_seed_and_mutate.sql
echo "✅ Mutations executed"

echo "== List kafka topics =="
docker exec -i cdc-kafka kafka-topics --bootstrap-server kafka:9092 --list | sort | sed -n '1,200p'
echo "✅ Topics listed"