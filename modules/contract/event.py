from sql import Cast, Literal
from sql.functions import Substring, Position

from trytond import backend
from trytond.pool import PoolMeta
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
    'EventLog',
    ]


class EventTypeAction:
    __name__ = 'event.type.action'

    def get_contracts_from_object(self, object_):
        contracts = []
        if object_.__name__ == 'contract':
            contracts = [object_]
        elif object_.__name__ == 'contract.option':
            if object_.parent_contract:
                contracts = [object_.parent_contract]
        return contracts

    def get_targets_and_origin_from_object_and_template(self, object_,
            template):
        if template.on_model and template.on_model.model == 'contract':
            contracts = self.get_contracts_from_object(object_)
            if contracts:
                return contracts, self.get_report_origin(object_, template)
        return super(EventTypeAction,
            self).get_targets_and_origin_from_object_and_template(object_,
                template)

    def get_filtering_objects_from_event_object(self, event_object):
        return super(EventTypeAction,
            self).get_filtering_objects_from_event_object(
                event_object) + self.get_contracts_from_object(event_object)

    def get_templates_list(self, filtering_object):
        if filtering_object.__name__ == 'contract':
            return filtering_object.product.report_templates
        return super(EventTypeAction, self).get_templates_list(
            filtering_object)


class EventLog:
    __name__ = 'event.log'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE',
        select=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        event_h = TableHandler(cls, module_name)
        to_migrate = event_h.column_exist('contract')

        super(EventLog, cls).__register__(module_name)

        # Migration from 1.4 : Set contract field
        if to_migrate:
            event_log = cls.__table__()
            to_update = cls.__table__()
            update_data = event_log.select(Cast(Substring(event_log.object_,
                        Position(',', event_log.object_) + Literal(1)),
                    cls.id.sql_type().base).as_('contract_id'), event_log.id,
                    where=event_log.object_.like('contract,%'))
            cursor.execute(*to_update.update(
                    columns=[to_update.contract],
                    values=[update_data.contract_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_event_keys(cls, objects):
        cur_dicts = super(EventLog, cls).get_event_keys(objects)
        for object_, log_dicts in cur_dicts.items():
            contracts = [x for x in
                cls.get_related_instances(object_, 'contract') if x]
            if not contracts:
                continue
            new_dicts = []
            for log_dict in log_dicts:
                for contract in contracts:
                    new_dict = log_dict.copy()
                    new_dict['contract'] = contract.id
                    new_dicts.append(new_dict)
            cur_dicts[object_] = new_dicts
        return cur_dicts

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name != 'contract':
            return super(EventLog, cls).get_related_instances(object_,
                model_name)
        if object_.__name__ == 'contract':
            return [object_]
        if object_.__name__ == 'contract.option':
            return [object_.parent_contract]
        if object_.__name__ == 'report_production.request':
            return cls.get_related_instances(object_.object_, 'contract')
        raise NotImplementedError
