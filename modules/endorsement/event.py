from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinitionReportTemplate',
    'Event',
    ]


class EndorsementDefinitionReportTemplate(model.CoopSQL, model.CoopView):
    'Endorsement Definition Report Template Relation'
    __name__ = 'endorsement.definition-report.template'

    definition = fields.Many2One('endorsement.definition',
        'Endorsement Definition', ondelete='RESTRICT',
        required=True, select=True)
    report_template = fields.Many2One('report.template', 'Report Template',
        ondelete='RESTRICT', required=True, select=True)


class Event:
    __name__ = 'event'

    @classmethod
    def get_contracts_from_object(cls, object_):
        contracts = super(Event, cls).get_contracts_from_object(object_)
        if object_.__name__ == 'endorsement':
            contracts.extend(object_.contracts)
        return contracts

    @classmethod
    def get_endorsements_from_object(cls, object_):
        endorsements = []
        if object_.__name__ == 'endorsement':
            endorsements = [object_]
        return endorsements

    @classmethod
    def get_filtering_objects_from_event_object(cls, event_object):
        return super(Event, cls).get_filtering_objects_from_event_object(
            event_object) + cls.get_endorsements_from_object(event_object)

    @classmethod
    def get_templates_list(cls, filtering_object):
        if filtering_object.__name__ == 'endorsement':
            return filtering_object.definition.report_templates
        return super(Event, cls).get_templates_list(filtering_object)
