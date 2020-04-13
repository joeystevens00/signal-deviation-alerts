from typing import Optional

from pydantic import BaseSettings
import redis


class Settings(BaseSettings):
    glassnode_api_key: Optional[str]
    redis_host: str = '127.0.0.1'
    redis_port: int = 6379

    class Config:
        env_file = '.env'


def redis_handle():
    settings = Settings().dict()
    return redis.Redis(
        host=settings['redis_host'],
        port=settings['redis_port'],
    )
