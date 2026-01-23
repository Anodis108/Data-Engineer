# run
# chmod +x tests/20_kafka_consume_cdc.sh

# # 1) list topics
# docker exec -it cdc-kafka kafka-topics --bootstrap-server kafka:9092 --list | sort

# # 2) consume đúng topic CDC
# ./tests/20_kafka_consume_cdc.sh pgserver1.public.customers


#!/usr/bin/env bash
set -euo pipefail

TOPIC="${1:-}"

if [ -z "$TOPIC" ]; then
  echo "Usage: $0 <topic_name>"
  echo "Hint: list topics:"
  echo "  docker exec -it cdc-kafka kafka-topics --bootstrap-server kafka:9092 --list | sort"
  exit 1
fi

echo "== Consuming CDC topic: $TOPIC =="
echo "(Ctrl+C to stop)"
docker exec -it cdc-kafka kafka-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic "$TOPIC" \
  --from-beginning \
  --timeout-ms 20000
