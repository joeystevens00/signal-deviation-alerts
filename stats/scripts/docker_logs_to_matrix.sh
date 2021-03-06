while read LINE; do export "$LINE"; done < /app/env

sleep $((RANDOM/1000))

for container in $(\
  docker container ls\
    | rev | awk '{print $1}' | rev\
    | grep -vE '^NAMES$'\
    | grep -vi synapse\
)
do
  docker container logs --since 5m $container\
    | python3 /app/src/log.py --host "$MATRIX_HOST" --user "$MATRIX_USER" --room docker_logs_$container
done
