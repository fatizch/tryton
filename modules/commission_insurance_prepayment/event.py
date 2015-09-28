from trytond.pool import PoolMeta, Pool

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
        super(Event, cls).notify_events(objects, event_code, description,
            **kwargs)
