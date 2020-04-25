set -eux

while read LINE; do export "$LINE"; done < /app/env

docker container ls\
  | rev | awk '{print $1}' | rev\
  | grep -vE '^NAMES$'\
  | grep -vi synapse\
  | xargs -I{} bash -c \
    'docker container logs --since 1m {} | python3 /app/src/log.py --host "$host" --user "$user" --password "$password" --room docker_logs_{}'
