while read LINE; do export "$LINE"; done < /app/env

sleep $((RANDOM/1000))

for service in $(\
  docker service ls \
    | awk '{print $2}'\
    | grep -vE '^NAME$'\
    | grep -vi synapse\
)
do
  docker service logs --since 5m "$service"\
    | python3 /app/src/log.py --host "$MATRIX_HOST" --user "$MATRIX_USER" --room docker_$service
done
