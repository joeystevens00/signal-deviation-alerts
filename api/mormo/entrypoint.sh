function wait_for_service {
  down=$(curl $host 2>&1 | grep 'Connection refused')
  if [[ "$down" ]]; then
    sleep 1
    wait_for_service
  fi
}
wait_for_service

curl $host/openapi.json > openapi.json
mormo run -i openapi.json --test --host $host -t $file --verbose
