import asyncio
from typing import Optional
import json
import random
import os
import logging

from fastapi import FastAPI
import pydantic
from pydantic import BaseModel, BaseSettings
from starlette.responses import Response
from uvicorn.config import Config
from uvicorn.main import Server

from alerts import MatrixLog
from log import main as send_matrix_message
from api import API
from util import redis_handle

app = FastAPI(version='0.1.0')

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=os.getenv('LOG_LEVEL', 'WARNING'),
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    matrix_user: str
    matrix_host: str
    matrix_password: str


class MessageInjest(BaseModel):
    room: str
    message: str


class Message(MessageInjest):
    host: str
    user: str
    password: str


class MessageDelivery(BaseModel):
    message: MessageInjest
    attempts: int = 0
    max_attempts: int = 10


async def sleep_time():
    asyncio.sleep(random.choice(range(1000, 5000))/1000)


async def dequeue_messages():
    async def dequeue():
        r = redis_handle()
        m = r.rpop('injest')
        if not m:
            await sleep_time()
            return (await dequeue())
        try:
            logger.debug("Dequeue")
            settings = Settings()
            d = json.loads(m.decode('utf-8'))
            logger.debug(f"Processing message: {d}")
            if d['attempts'] >= d['max_attempts']:
                logger.warning("Max tries hit for message.")
                logger.debug(f"Message content: {d}")
                await sleep_time()
                return (await dequeue())
            ret = await send_matrix_message(Message(
                **d['message'],
                host=settings.matrix_host,
                password=settings.matrix_password,
                user=settings.matrix_user
            ))
            logger.debug(f"Sent message and got back: {ret}")
        except Exception as e:
            logger.warning(f"Caught an error while sending message: {e}")
            if type(e) == pydantic.error_wrappers.ValidationError:
                logger.warning("Bad message encountered")
                logger.debug(f"Bad message content: {m}")
            else:
                r.rpush('injest', m)
        await sleep_time()
        return (await dequeue())
    try:
        await dequeue()
    except Exception as e:
        logger.warning(f"Caught an error while running dequeue: {e}")
        await sleep_time()
        return (await dequeue_messages())


@app.post("/")
async def save_message(m: MessageInjest):
    """Save message."""
    api = API()
    logger.debug(f"Enqueue message: {m}")
    if not api.tasks.get('dequeue'):
        logger.debug("Initializing dequeue task")
        api.tasks['dequeue'] = asyncio.ensure_future(dequeue_messages())
    delivery = MessageDelivery(message=m)
    return redis_handle().lpush('injest', delivery.json())


def start_uvicorn():
    config = Config(app=app, host="0.0.0.0", port='9000', loop="asyncio", log_level=logger.level)
    server = Server(config=config)
    logger.debug("Starting up the message queue")
    server.run()


if __name__ == '__main__':
    start_uvicorn()
