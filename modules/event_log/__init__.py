# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import event_log
from . import configuration


def register():
    Pool.register(
        event_log.EventTypeAction,
        event_log.EventLog,
        event_log.Trigger,
        event_log.Event,
        configuration.EventAggregateDescription,
        module='event_log', type_='model')
