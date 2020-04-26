#!/bin/bash
while read LINE; do export "$LINE"; done < /app/env
export MATRIX_PASSWORD="$password"

bash /app/docker_logger/scripts/stats.sh\
  | python3 /app/src/log.py --host "$host" --user "$user" --room server_stats
