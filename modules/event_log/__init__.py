# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .event_log import *


def register():
    Pool.register(
        EventLog,
        Trigger,
        Event,
        module='event_log', type_='model')
