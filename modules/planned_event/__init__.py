# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import planned_event
from . import rule_engine
from . import event


def register():
    Pool.register(
        planned_event.PlannedEvent,
        event.EventTypeActionPlannedEventType,
        event.EventTypeAction,
        rule_engine.RuleEngine,
        batch.ProcessPlannedEvent,
        module='planned_event', type_='model')
