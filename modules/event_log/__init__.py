from trytond.pool import Pool
from .event_log import *


def register():
    Pool.register(
        EventLog,
        Trigger,
        Event,
        module='event_log', type_='model')
