#!/bin/bash
while read LINE; do export "$LINE"; done < /app/env

bash /app/docker_logger/scripts/stats.sh\
  | python3 /app/src/log.py --host "$MATRIX_HOST" --user "$MATRIX_USER" --room server_stats
