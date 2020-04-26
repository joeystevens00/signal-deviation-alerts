#!/bin/bash
function format_space {
  cat - | awk '{
      ("numfmt " "--to=iec " $3) | getline used;
      ("numfmt " "--to=iec " $2) | getline total;
      print used,"of",total,"(", $3/$2*100, ")%";
    }'
}

echo -n 'Disk usage: '; df -B1 -t ext4 --total --output=fstype,size,used,avail | tail -1 | format_space
echo -n 'Load Average: '; uptime  | rev | cut -d ':' -f1 | rev
echo -n 'Memory Usage: '; free -b | grep 'Mem:' |  format_space
