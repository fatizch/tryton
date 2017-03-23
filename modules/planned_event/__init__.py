# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import batch
import planned_event
import rule_engine


def register():
    Pool.register(
        planned_event.EventPlanningConfigurationMixin,
        planned_event.PlannedEvent,
        rule_engine.RuleEngine,
        batch.ProcessPlannedEvent,
        module='planned_event', type_='model')
