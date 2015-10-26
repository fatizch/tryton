from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'EventTypeAction',
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
