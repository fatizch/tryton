# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast, Literal
from sql.functions import Substring, Position

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    'EventLog',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    def get_contracts_from_object(self, object_):
        contracts = super(EventTypeAction,
            self).get_contracts_from_object(object_)
        if object_.__name__ == 'contract.set':
            contracts.extend(object_.contracts)
        return contracts

    def get_contract_sets_from_object(self, object_):
        contract_sets = []
        if object_.__name__ == 'contract.set':
            contract_sets = [object_]
        elif object_.__name__ == 'contract':
            if object_.contract_set:
                contract_sets = [object_.contract_set]
        else:
            contracts = self.get_contracts_from_object(object_)
            if contracts:
                contract_sets = self.get_contract_sets_from_object(
                    contracts[0])
        return contract_sets

    def get_targets_and_origin_from_object_and_template(self,
            object_, template):
        if template.on_model and template.on_model.model == 'contract.set':
            contract_sets = self.get_contract_sets_from_object(object_)
            if contract_sets:
                return contract_sets, self.get_report_origin(object_, template)
        return super(EventTypeAction,
            self).get_targets_and_origin_from_object_and_template(object_,
                template)


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
            contract = pool.get('contract').__table__()
            update_data = event_log.join(contract, condition=(
                    Cast(Substring(event_log.object_, Position(',',
                                event_log.object_) + Literal(1)),
                    cls.id.sql_type().base) == contract.contract_set)
                ).select(contract.id.as_('contract_id'), event_log.id,
                where=event_log.object_.like('contract.set,%'))
            cursor.execute(*to_update.update(
                    columns=[to_update.contract],
                    values=[update_data.contract_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'contract' and object_.__name__ == 'contract.set':
            return list(object_.contracts)
        return super(EventLog, cls).get_related_instances(object_, model_name)
