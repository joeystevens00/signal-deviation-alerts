import asyncio
import aiohttp
import argparse
from datetime import datetime
import functools
import json
import pickle
import os
import socket
import subprocess
import sys
import logging

from nio import AsyncClient
from nio.responses import RoomResolveAliasResponse

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

state_file = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'state.pickle',
)

@functools.lru_cache()
def get_state():
    if os.path.exists(state_file):
        logger.debug(f"Getting state from {state_file}")
        with open(state_file, 'rb') as f:
            return pickle.loads(f.read())
    return {'rooms': {}}


def save_state(state):
    get_state.cache_clear()
    with open(state_file, 'wb') as f:
        f.write(pickle.dumps(state))


def shell_exec(cmd_str):
    res = subprocess.run(
        args=cmd_str.split(" "),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    stderr = res.stderr.decode('utf-8')
    if stderr:
        raise ValueError(f"Command failed ({cmd_str}): {stderr}")
    return res.stdout.decode('utf-8').rstrip("\n")


def format_message(m):
    hostname = socket.gethostname()
    if os.getenv('DOCKER_HOSTNAMES'):
        docker_hostname = shell_exec("docker info -f {{.Name}}")
        hostname = f"{hostname}.{docker_hostname}"
    return f"{datetime.utcnow()} ({hostname}): {m}"


def read_data():
    data = sys.stdin.readlines()
    if not data:
        raise ValueError("Expected STDIN since no message flag provided")
    return "\n".join(s.strip("\n") for s in data)


async def get_client(args):
    client = AsyncClient(args.host, args.user)
    if args.password:
        await client.login(
              args.password,
          )
    return client


async def get_room(args, alias):
    logger.debug(f"Get room with alias {alias}")
    state = get_state()
    room = state['rooms'].get(alias)
    client = await get_client(args)
    if room:
        logger.debug(f"Returning cached room_id for {alias}: {room}")
        await client.close()
        return room
    resolve_response = await client.room_resolve_alias(f'#{alias}:{args.host.lstrip("https://")}')
    if isinstance(resolve_response, RoomResolveAliasResponse):
        logger.debug(f"resolved {alias} to {resolve_response.room_id}")
        state['rooms'][alias] = resolve_response.room_id
    else:
        room = await client.room_create(alias=alias, name=alias, topic='log', federate=False)
        logger.debug(f"created {alias} to {room.room_id}")
        state['rooms'][alias] = room.room_id
    save_state(state)
    await client.close()
    return state['rooms'][alias]


async def main(args):
    room = await get_room(args, args.room)
    client = await get_client(args)
    ret = await client.room_send(
        room_id=room,
        message_type="m.room.message",
        content={
            "msgtype": "m.text",
            "body": format_message(args.message),
        }
    )
    await client.close()
    return ret


async def enqueue(args):
    session = aiohttp.ClientSession()
    url = os.getenv('MESSAGE_QUEUE')
    if not url:
        raise ValueError("MESSAGE_QUEUE environment variable is not set!")
    async with session.post(url, data=args.__dict__) as response:
        status = response.status
        data = await response.text()
        if status != 200:
            logger.warning(f"Error communicating with signal API (HTTP Code {status}): {data}")
        assert status == 200
        return url, data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Matrix Logger')
    parser.add_argument('--host', required=True, help='Synapse host.')
    parser.add_argument('--room', required=True, help='Room to send to.')
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', default=os.environ.get("MATRIX_PASSWORD"), help='User password. Defaults to MATRIX_PASSWORD environment variable')
    parser.add_argument('--message', default=read_data(), help='Message to send. Defaults to STDIN')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel('DEBUG')
    asyncio.get_event_loop().run_until_complete(enqueue(args))
