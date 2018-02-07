# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast, Literal
from sql.functions import Substring, Position

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'EventLog',
    ]


class EventLog:
    __metaclass__ = PoolMeta
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        event_h = TableHandler(cls, module_name)
        to_migrate = not event_h.column_exist('contract')

        super(EventLog, cls).__register__(module_name)

        # Migration from 1.4 : Set contract field
        if to_migrate:
            pool = Pool()
            event_log = cls.__table__()
            to_update = cls.__table__()
            payment = pool.get('account.payment').__table__()
            move_line = pool.get('account.move.line').__table__()
            update_data = event_log.join(payment, condition=(
                    Cast(Substring(event_log.object_, Position(',',
                                event_log.object_) + Literal(1)),
                    cls.id.sql_type().base) == payment.id)
                ).join(move_line, condition=(payment.line == move_line.id)
                ).select(move_line.contract.as_('contract_id'), event_log.id,
                where=event_log.object_.like('account.payment,%'))
            cursor.execute(*to_update.update(
                    columns=[to_update.contract],
                    values=[update_data.contract_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'contract' and object_.__name__ == 'account.payment':
            return [object_.line.contract] if object_.line else []
        return super(EventLog, cls).get_related_instances(object_, model_name)
