while read LINE; do export "$LINE"; done < /app/env

for container in $(\
  docker container ls\
    | rev | awk '{print $1}' | rev\
    | grep -vE '^NAMES$'\
    | grep -vi synapse\
    | xargs -I{} bash -c \
)
do
  docker container logs --since 5m $container\
    | python3 /app/src/log.py --host "$MATRIX_HOST" --user "$MATRIX_USER" --room docker_logs_$container
done
