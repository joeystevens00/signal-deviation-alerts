### Signal Deviation Alerts
[![Build Status](https://travis-ci.com/joeystevens00/signal-deviation-alerts.svg?branch=master)](https://travis-ci.com/joeystevens00/signal-deviation-alerts)

Trigger an action when a signal deviates more than a percentage.


Example with matrix-room action:
```
- condition:
    signal: btc_price
    timeframe:
      hours: 4
    difference: 2
  room: btc_price_alerts
  message: BTC Price ({{ last }}) moved {{ direction }} {{ diff }}% in the last 4 hours ({{ first }}).
```

Would send messages to the room `btc_price_alerts` like:

```
BTC Price (6935.59) moved down 4.0% in the last 4 hours (7179.4).
BTC Price (6955.86) moved up 2.0% in the last 4 hours (6850.31).
```

See `alerts.yaml` for more examples

Avaiable Actions
```
$ python3 alerts.py --help
...
matrix-room
stdout
```

Available Signals

```
$ python3 alerts.py list-signals
server_load_1m
server_load_5m
server_load_15m
server_memory_usage_percentage
server_memory_usage_used
server_memory_usage_free
server_disk_usage_percent
server_disk_usage_free
server_disk_usage_used
btc_price
btc_stock_to_flow
```
