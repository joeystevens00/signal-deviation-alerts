import asyncio
from typing import Optional
import json
from fastapi import FastAPI
from pydantic import BaseModel, BaseSettings
import redis
from starlette.responses import Response
from uvicorn.config import Config
from uvicorn.main import Server

from alerts import MatrixLog, send_matrix_message, get_schedule
from log import logger

app = FastAPI(version='0.1.0')


class Settings(BaseSettings):
    redis_host: str = '127.0.0.1'
    redis_port: int = 6379
    matrix_user: str
    matrix_host: str
    matrix_password: str


def redis_handle():
    settings = Settings().dict()
    return redis.Redis(
        host=settings['redis_host'],
        port=settings['redis_port'],
    )


class MessageContent(BaseModel):
    msgtype: str
    body: str


class Message(BaseModel):
    room_id: str
    message_type: str
    content: MessageContent


@app.post("/message")
def save_message(m: Message):
    """Save message."""
    return redis_handle().lpush('injest', m.json())


async def dequeue():
    logger.debug("Dequeue")
    r = redis_handle()
    m = r.rpop('injest').decode('utf-8')
    d = json.loads(m)
    try:
        send_matrix_message(Message(**d))
    except Exception as e:
        r.rpush('injest', m)
        logger.warning(f"Caught an error while sending message: {e}")


def start_uvicorn():
    config = Config(app=app, host="0.0.0.0", port='9000', loop="asyncio")
    server = Server(config=config)
    schedule = get_schedule()
    refresh_task = schedule(
        dequeue,
        interval=1,
    )
    server.run()


if __name__ == '__main__':
    start_uvicorn()
