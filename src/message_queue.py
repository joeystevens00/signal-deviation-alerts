import asyncio
from typing import Optional
import json
from fastapi import FastAPI
import pydantic
from pydantic import BaseModel, BaseSettings
from starlette.responses import Response
from uvicorn.config import Config
from uvicorn.main import Server

from alerts import MatrixLog, send_matrix_message
from log import logger
from api import API
from util import redis_handle

app = FastAPI(version='0.1.0')


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


async def dequeue():
    try:
        logger.debug("Dequeue")
        settings = Settings()
        r = redis_handle()
        m = r.rpop('injest').decode('utf-8')
        d = json.loads(m)
        logger.debug(f"Processing message: {d}")
        ret = await send_matrix_message(Message(
            **d,
            host=settings.matrix_host,
            password=settings.matrix_password,
            user=settings.matrix_user
        ))
        logger.debug(f"Sent message and got back: {ret}")
    except Exception as e:
        logger.warning(f"Caught an error while sending message: {e}")
        if e == pydantic.error_wrappers.ValidationError:
            logger.warning(f"Bad message encountered: {d}")
        print(type(e))
        print(dir(e))
        r.rpush('injest', m)
    await asyncio.sleep(1)
    return (await dequeue())

@app.post("/message")
async def save_message(m: MessageInjest):
    """Save message."""
    api = API()
    if not api.tasks.get('dequeue'):
        api.tasks['dequeue'] = asyncio.ensure_future(dequeue())
    return redis_handle().lpush('injest', m.json())


def start_uvicorn():
    config = Config(app=app, host="0.0.0.0", port='9000', loop="asyncio", log_level=logger.level)
    server = Server(config=config)
    server.run()


if __name__ == '__main__':
    start_uvicorn()
