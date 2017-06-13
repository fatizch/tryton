# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from itertools import groupby

from sql import Literal

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'ProcessPlannedEvent',
    ]


class ProcessPlannedEvent(batch.BatchRoot):
    'Process Planned Event'
    __name__ = 'planned.event.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'planned.event'

    @classmethod
    def select_ids(cls, treatment_date):
        pool = Pool()
        planned_event = pool.get('planned.event').__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*planned_event.select(planned_event.id,
                planned_event.event_type, planned_event.on_object,
                where=((planned_event.planned_date <= treatment_date) &
                    (planned_event.processed == Literal(False))),
                order_by=[planned_event.event_type,
                    planned_event.on_object]))
        ids = []

        def grouping_key(x):
            return (x[1], x[2].split(',')[0])

        for key, values in groupby(((p_id, event_id, obj) for p_id, event_id,
                obj in cursor.fetchall()), grouping_key):
            ids.append([x[:1] for x in values])
        return ids

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        return [x.id for x in Pool().get('planned.event').process(objects)]
