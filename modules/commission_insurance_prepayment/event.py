# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.server_context import ServerContext

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    ]


class Event:
    __name__ = 'event'

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        pool = Pool()
        Contract = pool.get('contract')
        if event_code == 'activate_contract':
            Contract.create_prepayment_commissions(objects, adjustement=False)
        elif event_code == 'reactivate_contract':
            with ServerContext().set_context(reactivate=True):
                Contract.create_prepayment_commissions(objects,
                    adjustement=True)
        super(Event, cls).notify_events(objects, event_code, description,
            **kwargs)
