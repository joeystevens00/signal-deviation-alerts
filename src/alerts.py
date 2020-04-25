import atexit
import asyncio
import argparse
from datetime import datetime, timedelta
import enum
import functools
import hashlib
import os
import sys
from typing import Any, List, Optional

import click
import jinja2
import pandas as pd
from pandas import DataFrame, Timestamp, Timedelta
from model import BaseModel
import yaml


from log import main as send_matrix_message, logger
from signals import SignalMap, EOF
from util import Borg, get_deviation_percentage, schedule_func

class MatrixConfig(BaseModel):
    host: str
    user: str
    password: str


class MatrixLog(MatrixConfig):
    message: str
    room: str


def render_message(alert, signal_reading):
    return jinja2.Template(alert.message).render(
        **alert.dict(),
        **signal_reading.dict(),
        direction='up' if signal_reading.increased else 'down',
    )


async def send_to_file(alert, signal_reading, file):
    with open(file, 'a') as f:
        f.write(render_message(alert, signal_reading) + "\n")


async def send_to_stdout(alert, signal_reading):
    print(render_message(alert, signal_reading))


async def send_to_matrix_room(alert, signal_reading, matrix_config):
    message = render_message(alert, signal_reading)
    logger.debug(f"Sending {alert} message {message}")
    matrix_log = {**matrix_config.dict(), 'message': message, 'room': alert.room}
    ret = await send_matrix_message(
        MatrixLog(**matrix_log)
    )
    logger.debug(f"Alert finished {ret}")


class DeviationCondition(BaseModel):
    signal: str
    timeframe: dict
    difference: int


class SignalReading(BaseModel):
    first: float
    last: float
    increased: bool
    diff: float

    def __str__(self):
        return f"<SignalReading first={round(self.first, 3)}, last={round(self.last, 3)}, diff={round(self.diff, 3)}, increased={self.increased}>"


class SignalStrategy(enum.Enum):
    oldest_newest = 'oldest_newest'
    min_max = 'min_max'


def signal_strategy_oldest_newest(df):
    return (
        float(df.sort_index(ascending=False).tail(1).iloc[0]),
        float(df.sort_index(ascending=False).head(1).iloc[0]),
    )


def signal_strategy_min_max(df):
    return (
        df['value'].min(),
        df['value'].max(),
    )


class Alert(BaseModel):
    condition: DeviationCondition
    message: str
    room: Optional[str]
    last_notified: Optional[datetime]
    cooloff: Optional[timedelta]
    poll_rate: int = 60
    signal_read_strategy: SignalStrategy = SignalStrategy.oldest_newest

    @property
    def id(self):
        return hashlib.sha256(repr(self.dict()).encode('utf-8')).hexdigest()

    @property
    def timeframe(self):
        return timedelta(**self.condition.timeframe)

    @property
    def timeframe_pd(self):
        return Timedelta(**self.condition.timeframe)

    @classmethod
    def load_collection(cls, file):
        with open(file) as f:
            data = yaml.safe_load(f.read())
        alerts = []
        for alert in data:
            alerts.append(
                cls(condition=DeviationCondition(**alert.pop('condition')), **alert)
            )
        return alerts

    def __str__(self):
        return f'Alert<{self.condition.signal} {self.condition.difference}% in {self.timeframe}>'

    @property
    def signal_read_strategy_func(self):
        m = {
            SignalStrategy.oldest_newest: signal_strategy_oldest_newest,
            SignalStrategy.min_max: signal_strategy_min_max,
        }
        return m[self.signal_read_strategy]


class Alerts:
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        try:
            self.data
        except AttributeError:
            self.data = {}
        try:
            self.api
        except AttributeError:
            self.api = {}


def load_signal_database(dir):
    logger.debug(f"Loading signal database: {dir}")
    alerts = Alerts()
    for path in os.path.os.listdir(dir):
        if path.endswith('.hdf5'):
            alert_id = path.split('.')[0]
            alerts.data[alert_id] = pd.read_hdf(os.path.join(dir, path), alert_id)


class AlertTask:
    def __init__(self, loop, alert, signal, alert_action):
        self.loop = loop
        self.alert = alert
        self.signal = signal
        self.signal_name = alert.condition.signal.lower()
        self.alert_action = alert_action

    def __str__(self):
        return f"<AlertTask {self.alert}>"

    @classmethod
    def injest_reading(cls, signal_name, signal_value):
        alerts = Alerts()
        data_in = DataFrame([{
            'timestamp': Timestamp.utcnow(),
            'value': signal_value
        }]).set_index('timestamp')
        if alerts.data.get(signal_name) is None:
            alerts.data[signal_name] = data_in
        else:
            alerts.data[signal_name] = pd.concat([alerts.data[signal_name], data_in])
        return alerts.data[signal_name]

    def truncate_to_alert_timeframe(self, df):
        # Truncate to only data in the timeframe
        return df[Timestamp.utcnow()-self.alert.timeframe_pd<df.index].dropna()

    async def injest(self):
        signal_value = await self.signal()
        return self.injest_reading(self.signal_name, signal_value)

    async def _calculate_signal_deviation(self, df):
        # first, last
        # oldest, newest
        # min, max
        first, last = self.alert.signal_read_strategy_func(df)

        diff = get_deviation_percentage(first, last)
        signal_reading = SignalReading(
            first=float(first),
            last=float(last),
            increased=float(first)<float(last),
            diff=float(diff),
        )
        logger.debug(f"{self}: considering alerting ({self.alert.condition.difference} <= {diff}) for {signal_reading}")
        if self.alert.condition.difference <= diff:
            cooloff = self.alert.cooloff or self.alert.timeframe
            logger.debug(f"{self}: Cmp {self.alert.last_notified} and {datetime.utcnow()} - {self.alert.last_notified} < {cooloff}")
            if self.alert.last_notified and datetime.utcnow() - self.alert.last_notified < cooloff:
                logger.debug(f"Alerted within the cooloff period ({cooloff}), skipping alert ({self.alert})...")
                return
            self.alert.last_notified = datetime.utcnow()
            try:
                await self.alert_action(
                    self.alert,
                    signal_reading,
                )
            except Exception as e:
                logger.error(f"{self}: Error in alert_action: {e}")
                raise e

    async def __call__(self):
        try:
            df = await self.injest()
            df = self.truncate_to_alert_timeframe(df)
        except Exception as e:
            logger.debug(f"Error in injest: {e}")
            raise e
        try:
            await self._calculate_signal_deviation(df)
        except Exception as e:
            logger.debug(f"Error in _calculate_signal_deviation: {e}")
            raise e


def save_signal_database(datadir):
    import warnings
    import tables
    original_warnings = list(warnings.filters)
    warnings.simplefilter('ignore', tables.NaturalNameWarning)
    alerts = Alerts()
    for alert_id, df in alerts.data.items():
        filename=f'{alert_id}.hdf5'
        filepath=os.path.join(datadir, filename)
        df.to_hdf(filepath, alert_id)
    warnings.filters = original_warnings

async def save_signal_database_async(datadir):
    return save_signal_database(datadir)


@click.group()
@click.option('-v', '--verbose', 'verbose', is_flag=True)
def cli(verbose):
    """Signal Deviation Alerts."""
    if verbose:
        logger.setLevel('DEBUG')


def create_register_alert_task(alert, loop, schedule, func, **kwargs):
    signals = SignalMap()
    print("alert condition ", alert.condition)
    signal = signals.value[alert.condition.signal.lower()]
    update = AlertTask(
        loop=loop,
        signal=signal(loop=loop),
        alert=alert,
        alert_action=functools.partial(
            func,
            **kwargs,
        ),
    )
    refresh_task = schedule(
        update,
        interval=alert.poll_rate,
    )
    return update, refresh_task


def get_schedule(loop=None):
    create_scheduler = lambda loop: functools.partial(
        schedule_func, loop=loop,
    )
    return create_scheduler(
        loop=(loop or asyncio.get_event_loop())
    )


def process_alerts_from_file(datadir, file, func, **kwargs):
    logger.debug(f"Processing alerts from file {file}")
    loop = asyncio.new_event_loop()
    schedule = get_schedule(loop)

    for alert in Alert.load_collection(file):
        create_register_alert_task(alert, loop, schedule, func, **kwargs)

    save_db_task = schedule(
        functools.partial(save_signal_database_async, datadir=datadir),
    )
    atexit.register(functools.partial(save_signal_database, datadir=datadir))
    loop.run_forever()


@cli.command()
@click.option(
    '-d', '--datadir', 'datadir', type=click.Path(),
    help='Directory to save signal database to',
    default=os.path.join(os.path.dirname(os.path.realpath(__file__)), '../data'),
)
@click.option('-f', '--file', 'file', type=click.Path(),
              help='Alerts to load', required=True)
@click.option('-t', '--host', 'host', help='Synapse host', required=True)
@click.option('-u', '--user', 'user', help='Matrix username', required=True)
@click.option(
    '-p', '--password', 'password',
    help='Matrix User password. Defaults to MATRIX_PASSWORD environment variable',
    required=True,
    default=os.environ.get("MATRIX_PASSWORD"),
)
def matrix_room(datadir, file, host, user, password):
    if not datadir:
        datadir="/tmp/data"
        if not os.path.exists(datadir):
            os.mkdir(datadir)
    load_signal_database(datadir)
    matrix_config = MatrixConfig(
        host=host, user=user, password=password,
    )
    process_alerts_from_file(
        datadir, file, send_to_matrix_room,
        matrix_config=matrix_config,
    )


@cli.command()
@click.option(
    '-d', '--datadir', 'datadir', type=click.Path(),
    help='Directory to save signal database to',
    default=os.path.join(os.path.dirname(os.path.realpath(__file__)), '../data'),
)
@click.option('-f', '--file', 'file', type=click.Path(),
              help='Alerts to load', required=True)
def stdout(datadir, file):
    load_signal_database(datadir)
    process_alerts_from_file(
        datadir, file, send_to_stdout,
    )


@cli.command()
@click.option(
    '-d', '--datadir', 'datadir', type=click.Path(),
    help='Directory to save signal database to',
    default=os.path.join(os.path.dirname(os.path.realpath(__file__)), '../data'),
)
@click.option('-f', '--file', 'file', type=click.Path(),
              help='Alerts to load', required=True)
@click.option('-o', '--out', 'out', type=click.Path(),
              help='Path to save alerts to', required=True)
def file(datadir, file, out):
    load_signal_database(datadir)
    process_alerts_from_file(
        datadir, file, functools.partial(send_to_file, file=out),
    )


@cli.command()
def list_signals():
    print("\n".join(SignalMap().value.keys()))


if __name__ == "__main__":
    cli()
