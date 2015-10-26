from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinitionReportTemplate',
    'EventTypeAction',
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
