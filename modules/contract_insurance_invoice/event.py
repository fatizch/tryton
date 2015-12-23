from sql import Cast, Literal
from sql.functions import Substring, Position

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    'EventLog',
    'EventTypeAction',
    ]


class Event:
    __name__ = 'event'

    @classmethod
    def notify_events(cls, objects, event_code, description=None, **kwargs):
        pool = Pool()
        Contract = pool.get('contract')
        if event_code == 'activate_contract':
            Contract.invoice_non_periodic_premiums(objects,
                'at_contract_signature')
        super(Event, cls).notify_events(objects, event_code, description,
            **kwargs)


class EventLog:
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        event_h = TableHandler(cursor, cls, module_name)
        to_migrate = event_h.column_exist('contract')

        super(EventLog, cls).__register__(module_name)

        # Migration from 1.4 : Set contract field
        if to_migrate:
            pool = Pool()
            event_log = cls.__table__()
            to_update = cls.__table__()
            contract_invoice = pool.get('contract.invoice').__table__()
            update_data = event_log.join(contract_invoice, condition=(
                    Cast(Substring(event_log.object_, Position(',',
                                event_log.object_) + Literal(1)),
                    cls.id.sql_type().base) == contract_invoice.invoice)
                ).select(contract_invoice.contract.as_('contract_id'),
                    event_log.id,
                where=event_log.object_.like('account.invoice,%'))
            cursor.execute(*to_update.update(
                    columns=[to_update.contract],
                    values=[update_data.contract_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'contract' and object_.__name__ == 'account.invoice':
            return [object_.contract] if object_.contract else []
        return super(EventLog, cls).get_related_instances(object_, model_name)


class EventTypeAction:
    __name__ = 'event.type.action'

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('cancel_or_delete_non_periodic_invoices',
                'Cancel or Delete Non Periodic Invoices')]

    def filter_objects(self, objects):
        if self.action != 'cancel_or_delete_non_periodic_invoices':
            return super(EventTypeAction, self).filter_objects(objects)
        contracts = []
        for o in objects:
            contracts.extend(self.get_contracts_from_object(o))
        return super(EventTypeAction, self).filter_objects(contracts)

    def execute(self, objects, event_code):
        pool = Pool()
        Contract = pool.get('contract')
        if self.action != 'cancel_or_delete_non_periodic_invoices':
            return super(EventTypeAction, self).execute(objects, event_code)
        Contract.clean_up_contract_invoices(objects, non_periodic=True)
