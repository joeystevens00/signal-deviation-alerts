while read LINE; do export "$LINE"; done < /app/env

export MATRIX_PASSWORD="$password"

docker container ls\
  | rev | awk '{print $1}' | rev\
  | grep -vE '^NAMES$'\
  | grep -vi synapse\
  | xargs -I{} bash -c \
    'docker container logs --since 5m {} | python3 /app/src/log.py --host "$host" --user "$user" --room docker_logs_{}'
