import asyncio
import importlib
import hashlib
import json
from typing import Any, Iterable
import random

import redis
from pydantic import BaseSettings

from c import redis_handle
from log import logger

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
            race_buster = random.randint(1, 60000)/1000 # interval*1000 seems excessive when poll_rate is high
            await asyncio.sleep(race_buster, loop=loop)
            await func(*args, **kwargs)
            await asyncio.sleep(interval-race_buster, loop=loop)

    return loop.create_task(periodic_func())


def cls_from_str(name):
    # Import the module .
    components = name.split('.')
    module = importlib.import_module(
        '.'.join(components[:len(components) - 1]),
    )
    a = module.__getattribute__(components[-1])
    return a


def fingerprint(payload: Any):
    if isinstance(payload, Iterable) and not isinstance(payload, dict):
        payload = [p for p in payload]
    payload = repr(payload)
    return hashlib.sha512(payload.encode('utf-8')).hexdigest()


class DB:
    def __init__(self, r, model=None, uid=None):
        if uid:
            model = self.load_model_from_uid(r, uid)
            if not model:
                raise ValueError("Unable to load by uid")
        elif model:
            self.uid = fingerprint(model.dict())
        else:
            raise ValueError("Model or uid is required")
        self.model = model
        self.cache_ttl = 60 * 60 * 24 * 7
        self.klass = type(self.model).__module__ + '.'\
            + type(self.model).__name__
        self.json = json.dumps({
            'data': self.model.to_dict(),
            'class': self.klass,
        })
        self.r = r

    @classmethod
    def _get(cls, r, uid):
        logger.debug(f'Getting {uid} from Redis.')
        return r.get(uid).decode('utf-8')

    @classmethod
    def load_model_from_uid(cls, r, uid):
        raw = cls._get(r, uid)
        if raw:
            raw = json.loads(raw)
            return cls_from_str(raw['class'])(**raw['data'])

    def save(self):
        logger.debug(f'Creating {repr(self)} in Redis.')
        return self.r.setex(
            self.uid, self.cache_ttl,
            self.json.encode('utf-8'),
        )


def save_db(o):
    odb = DB(redis_handle(), model=o)
    if not odb.save():
        raise ValueError(f"Unable to save {o}(uid: {odb.uid}) to the DB.")
    logger.debug(f"New {type(o)}: {odb.uid}")
    return o.construct(**{'id': odb.uid, 'object': o.to_dict()})


def load_db(id):
    return DB.load_model_from_uid(redis_handle(), id)


class GlobalSettings(BaseSettings):
    redis_host: str = '127.0.0.1'
    redis_port: int = 6379


def redis_handle():
    settings = GlobalSettings().dict()
    return redis.Redis(
        host=settings['redis_host'],
        port=settings['redis_port'],
    )
