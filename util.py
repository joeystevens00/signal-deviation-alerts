import asyncio
import random

class Borg:
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state

def get_deviation_percentage(x, y):
    return round(abs((1 - (x / y))*100))


def schedule_func(func, args=None, kwargs=None, interval=60, *, loop):
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    async def periodic_func():
        while True:
            race_buster = random.randint(1, 60000)/1000 # interval*1000 seems excessive when signal_poll_rate is high
            await asyncio.sleep(race_buster, loop=loop)
            await func(*args, **kwargs)
            await asyncio.sleep(interval-race_buster, loop=loop)

    return loop.create_task(periodic_func())
