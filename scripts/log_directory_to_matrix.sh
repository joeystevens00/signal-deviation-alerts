#!/bin/bash
function minutes_ago {
  when=$(date --date="$1 minutes ago" '+%b %_d %H:%M')
  sed -n "/^$when/,\$p" $2
}
function log {
  python3 log.py --host https://somehost --user log --password "$PASSWORD" --room $1
}

for path in $(find /var/log -name *log -type f)
do
  # include subdir in name e.g. nginx_error
  name=$(echo $path | cut -d "/" -f4- | tr '/' '_')
  minutes_ago 1 $path | log $(echo $name | tr -d ".")
done
