import asyncio
from typing import Optional

from fastapi import FastAPI
from starlette.responses import Response
from uvicorn.config import Config
from uvicorn.main import Server

from alerts import (
    Alert, AlertTask, create_register_alert_task, get_schedule,
    MatrixConfig, send_to_matrix_room, SignalMap,
)
from log import logger
from model import BaseModel
from util import load_db, save_db

app = FastAPI(version='0.1.0')

# class Action(BaseModel):
#     action_id: str
#     alert_id: str

class Signal(BaseModel):
    name: str


class SignalData(BaseModel):
    name: str
    data: float


class MatrixAction(BaseModel):
    config_id: str
    alert_id: str


class SaveDB(BaseModel):
    id: str


class SaveAlertResult(SaveDB):
    object: Alert


class SaveMatrixResult(SaveDB):
    object: MatrixConfig


class SaveSignalResult(SaveDB):
    object: Signal


# class SaveActionResult(SaveDB):
#     object: Action


class SaveMatrixActionResult(SaveDB):
    object: MatrixAction


class API:
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        try:
            self.tasks
        except AttributeError:
            self.tasks = {}
        try:
            self.loop
        except AttributeError:
            self.loop = asyncio.get_event_loop()


# @app.post("/signal", response_model=SaveSignalResult)
# def new_signal(o: Signal) -> SaveSignalResult:
#     """New Schema."""
#     return save_db(o).to_dict()
#
#
# @app.get("/signal/{signal_id}", response_model=Signal)
# def get_signal(signal_id) -> Signal:
#     """Get Signal by ID."""
#     return load_db(signal_id)


@app.post("/signal/data", status_code=204, response_class=Response)
def injest_signal_data(o: SignalData) -> None:
    """Post a reading for a custom Signal."""
    if o.name in SignalMap().value.keys():
        return Response(content='Unable to injest data for builtin signals', status_code=403)
    AlertTask.injest_reading(o.name, o.data)


@app.post("/alert", response_model=SaveAlertResult)
def new_alert(o: Alert) -> SaveAlertResult:
    """New alert."""
    return save_db(o).to_dict()


@app.get("/alert/{alert_id}", response_model=Alert)
def get_alert(alert_id) -> Alert:
    """Get alert by ID."""
    return load_db(alert_id)


@app.post("/matrix/config", response_model=SaveMatrixResult)
def new_matrix_config(o: MatrixConfig) -> SaveMatrixResult:
    """New Matrix Config."""
    return save_db(o).to_dict()


@app.get("/matrix/config/{matrix_config_id}", response_model=MatrixConfig)
def get_matrix_config(matrix_config_id) -> MatrixConfig:
    """Get Matrix Config by ID."""
    return load_db(matrix_config_id)


@app.post("/matrix/action", response_model=SaveMatrixActionResult)
def new_matrix_action(o: MatrixAction) -> SaveMatrixActionResult:
    """New Matrix Action."""
    return save_db(o).to_dict()


@app.get("/matrix/action/{action_id}", response_model=MatrixAction)
def load_matrix_action(action_id: str) -> MatrixAction:
    """Get Matrix Action by ID."""
    return load_db(action_id)


@app.post("/matrix/action/{action_id}/register", status_code=204, response_class=Response)
async def register_matrix_action(action_id: str) -> None:
    """Register a matrix action."""
    api = API()
    loop = api.loop
    task_registry = api.tasks
    if task_registry.get(action_id):
        return Response(content=None, status_code=409)

    schedule = get_schedule(loop)
    action = load_db(action_id)
    matrix_config = load_db(action.config_id)
    alert = load_db(action.alert_id)
    update_task, refresh_task = create_register_alert_task(
        alert, loop, schedule,
        send_to_matrix_room,
        matrix_config=matrix_config,
    )
    task_registry[action_id] = True


def start_uvicorn():
    config = Config(app=app, host="0.0.0.0", loop="asyncio", log_level=logger.level)
    server = Server(config=config)
    server.run()



if __name__ == '__main__':
    start_uvicorn()
