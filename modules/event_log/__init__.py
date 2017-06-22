# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import event_log


def register():
    Pool.register(
        event_log.EventLog,
        event_log.Trigger,
        event_log.Event,
        module='event_log', type_='model')
