from datetime import datetime, timedelta
from concurrent.futures import ALL_COMPLETED
import functools
import json
import os
from typing import Optional

import asyncio
import aiohttp
import pandas as pd
import psutil

from log import main as send_matrix_message, logger
from util import Borg

from c import Settings

class SignalMap:
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        try:
            self.value
        except AttributeError:
            self.value = {}


class BtcPriceCache:
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        try:
            self.value
        except AttributeError:
            self.value = {}


def register_signal(name):
    def wrapper(func):
        signals = SignalMap()
        if not signals.value:
            signals.value = {}
        logger.debug(f"Register signal {name}")
        signals.value[name] = func
        logger.debug(f"Signals {signals.value}")
        return func
    return wrapper


class HttpSignal:
    def __init__(self, loop):
        self.loop = loop
        self.session = aiohttp.ClientSession(loop=loop)

    async def _fetch(self, url):
        async with self.session.get(url) as response:
            status = response.status
            data = await response.text()
            if status != 200:
                logger.warning(f"Error communicating with signal API (HTTP Code {status}): {data}")
            assert status == 200
            return url, data

    def __del__(self):
        self.session.close()


class LoadAvgSignal:
    def __init__(self, loop):
        self.loop = loop
        load_avg = os.getloadavg()
        self.load_avg_map = {
            1: load_avg[0],
            5: load_avg[1],
            15: load_avg[2]
        }

    def get_average(self, timeframe):
        return self.load_avg_map[timeframe]


class Signal:
    def __init__(self, loop):
        self.loop = loop


@register_signal('server_load_1m')
class LoadAvgOneMinute(LoadAvgSignal):
    async def __call__(self):
        return self.get_average(1)


@register_signal('server_load_5m')
class LoadAvgFiveMinute(LoadAvgSignal):
    async def __call__(self):
        return self.get_average(5)


@register_signal('server_load_15m')
class LoadAvgFifteenMinute(LoadAvgSignal):
    async def __call__(self):
        return self.get_average(15)


@register_signal('server_memory_usage_percentage')
class MemoryUsagePercentage(Signal):
    async def __call__(self):
        return psutil.virtual_memory().percent


@register_signal('server_memory_usage_used')
class MemoryUsageUsed(Signal):
    async def __call__(self):
        return psutil.virtual_memory().used


@register_signal('server_memory_usage_free')
class MemoryUsageFree(Signal):
    async def __call__(self):
        return psutil.virtual_memory().free


@register_signal('server_memory_swap_usage_percentage')
class MemorySwapUsagePercentage(Signal):
    async def __call__(self):
        return psutil.swap_memory().percent


@register_signal('server_memory_swap_usage_used')
class MemorySwapUsageUsed(Signal):
    async def __call__(self):
        return psutil.swap_memory().used


@register_signal('server_memory_swap_usage_free')
class MemorySwapUsageFree(Signal):
    async def __call__(self):
        return psutil.swap_memory().free


@register_signal('server_disk_usage_percent')
class DiskUsagePercent(Signal):
    async def __call__(self):
        return psutil.disk_usage('/').percent


@register_signal('server_disk_usage_free')
class DiskUsageFree(Signal):
    async def __call__(self):
        return psutil.disk_usage('/').free


@register_signal('server_disk_usage_used')
class DiskyUsageUsed(Signal):
    async def __call__(self):
        return psutil.disk_usage('/').used


@register_signal('btc_price')
class BTCPrice(HttpSignal):
    async def __call__(self):
        price_cache = BtcPriceCache()
        if price_cache.value:
            logger.debug(f"Cached BTC value {price_cache.value}")
            if (datetime.utcnow() - price_cache.value['timestamp']).total_seconds() < 60:
                logger.debug(f"Returning cached BTC price ({price_cache.value['value']}) from {price_cache.value['timestamp']}")
                return price_cache.value['value']
        logger.debug("Fetching price of BTC")
        tasks = [self._fetch('https://blockchain.info/ticker')]
        done, pending = await asyncio.wait(
            tasks,
            loop=self.loop,
            return_when=ALL_COMPLETED
        )
        for task in done:
            url, data = task.result()
            btc_price = json.loads(data)['USD']['last']
        price_cache.value = {'timestamp': datetime.utcnow(), 'value': btc_price}
        return btc_price

    def __str__(self):
        return "<Signal btc_price>"


@register_signal('btc_stock_to_flow')
class GlassnodeStockToFlowDeflection(HttpSignal):
    def __str__(self):
        return "<Signal btc_stock_to_flow>"

    async def __call__(self):
        config = Settings()
        logger.debug("Fetching the stock to flow deflection")
        tasks = [self._fetch(
            'https://api.glassnode.com'\
                f'/v1/metrics/indicators/stock_to_flow_deflection'\
                f'?a=BTC&api_key={config.glassnode_api_key}'
        )]
        done, pending = await asyncio.wait(
            tasks,
            loop=self.loop,
            return_when=ALL_COMPLETED
        )
        for task in done:
            url, data = task.result()
            data = json.loads(data)
        df = pd.DataFrame(data)
        df.loc[:, 't'] = pd.to_datetime(df['t'], unit='s')
        return float(df.set_index('t').last('1H')['v'])


EOF = None # Force python to read the whole file
