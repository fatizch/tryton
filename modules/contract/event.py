from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Event',
    ]


class Event:
    __name__ = 'event'

    @classmethod
    def get_contracts_from_object(cls, object_):
        contracts = []
        if object_.__name__ == 'contract':
            contracts = [object_]
        elif object_.__name__ == 'contract.option':
            if object_.parent_contract:
                contracts = [object_.parent_contract]
        return contracts

    @classmethod
    def get_targets_and_origin_from_object_and_template(cls, object_,
            template):
        if template.on_model and template.on_model.model == 'contract':
            contracts = cls.get_contracts_from_object(object_)
            if contracts:
                return contracts, cls.get_report_origin(object_, template)
        return super(Event,
            cls).get_targets_and_origin_from_object_and_template(object_,
                template)

    @classmethod
    def get_filtering_objects_from_event_object(cls, event_object):
        return super(Event, cls).get_filtering_objects_from_event_object(
            event_object) + cls.get_contracts_from_object(event_object)

    @classmethod
    def get_templates_list(cls, filtering_object):
        if filtering_object.__name__ == 'contract':
            return filtering_object.product.report_templates
        return super(Event, cls).get_templates_list(filtering_object)
