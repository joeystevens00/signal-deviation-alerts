function wait_for_service {
  down=$(curl $host 2>&1 | grep 'Connection refused')
  if [[ "$down" ]]; then
    sleep 1
    wait_for_service
  fi
}
wait_for_service

mormo test --target $host/openapi.json --config $file --verbose
