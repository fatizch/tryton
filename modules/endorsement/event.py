from sql import Cast, Literal
from sql.functions import Substring, Position

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinitionReportTemplate',
    'EventTypeAction',
    'EventLog',
    ]


class EndorsementDefinitionReportTemplate(model.CoopSQL, model.CoopView):
    'Endorsement Definition Report Template Relation'
    __name__ = 'endorsement.definition-report.template'

    definition = fields.Many2One('endorsement.definition',
        'Endorsement Definition', ondelete='RESTRICT',
        required=True, select=True)
    report_template = fields.Many2One('report.template', 'Report Template',
        ondelete='RESTRICT', required=True, select=True)


class EventTypeAction:
    __name__ = 'event.type.action'

    def get_contracts_from_object(self, object_):
        contracts = super(EventTypeAction,
            self).get_contracts_from_object(object_)
        if object_.__name__ == 'endorsement':
            contracts.extend(object_.contracts)
        return contracts

    def get_endorsements_from_object(self, object_):
        endorsements = []
        if object_.__name__ == 'endorsement':
            endorsements = [object_]
        return endorsements

    def get_filtering_objects_from_event_object(self, event_object):
        return super(EventTypeAction,
            self).get_filtering_objects_from_event_object(
                event_object) + self.get_endorsements_from_object(event_object)

    def get_templates_list(self, filtering_object):
        if filtering_object.__name__ == 'endorsement':
            return filtering_object.definition.report_templates
        return super(EventTypeAction, self).get_templates_list(
            filtering_object)


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
            contract_endorsement = pool.get('endorsement.contract').__table__()
            update_data = event_log.join(contract_endorsement, condition=(
                    Cast(Substring(event_log.object_, Position(',',
                                event_log.object_) + Literal(1)),
                    cls.id.sql_type().base) ==
                    contract_endorsement.endorsement)
                ).select(contract_endorsement.contract.as_('contract_id'),
                event_log.id, where=event_log.object_.like('endorsement,%'))
            cursor.execute(*to_update.update(
                    columns=[to_update.contract],
                    values=[update_data.contract_id],
                    from_=[update_data],
                    where=update_data.id == to_update.id))

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if model_name == 'contract' and object_.__name__ == 'endorsement':
            return [x.contract for x in object_.contract_endorsements]
        return super(EventLog, cls).get_related_instances(object_, model_name)
