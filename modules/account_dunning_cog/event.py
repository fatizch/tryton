from sql import Literal, Cast
from sql.functions import Substring, Position

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


__metaclass__ = PoolMeta
__all__ = [
    'EventLog',
    ]


class EventLog:
    __name__ = 'event.log'

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        event_h = TableHandler(cls, module_name)
        to_migrate = event_h.column_exist('contract')

        super(EventLog, cls).__register__(module_name)

        # Migration from 1.4 : Set contract field
        if to_migrate:
            pool = Pool()
            event_log = cls.__table__()
            to_update = cls.__table__()
            dunning = pool.get('account.dunning').__table__()
            move_line = pool.get('account.move.line').__table__()
            update_data = event_log.join(dunning, condition=(
                    Cast(Substring(event_log.object_, Position(',',
                                event_log.object_) + Literal(1)),
                    cls.id.sql_type().base) == dunning.id)
                ).join(move_line, condition=(dunning.line == move_line.id)
                ).select(move_line.contract.as_('contract_id'), event_log.id,
                where=event_log.object_.like('account.dunning,%'))
            cursor.execute(*to_update.update(
                    columns=[to_update.contract],
                    values=[update_data.contract_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'contract' and object_.__name__ == 'account.dunning':
            return [object_.line.contract]
        return super(EventLog, cls).get_related_instances(object_, model_name)
