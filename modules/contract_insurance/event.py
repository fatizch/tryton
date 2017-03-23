# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'EventTypeAction',
    'EventLog',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    def get_options_from_object(self, object_):
        if object_.__name__ == 'contract.option':
            return [object_]
        return []

    def get_targets_and_origin_from_object_and_template(self, object_,
            template):
        if template.on_model and template.on_model.model == 'contract.option':
            options = self.get_options_from_object(object_)
            if options:
                return options, self.get_report_origin(object_, template)
        return super(EventTypeAction,
            self).get_targets_and_origin_from_object_and_template(object_,
                template)

    def get_filtering_objects_from_event_object(self, event_object):
        return super(EventTypeAction,
            self).get_filtering_objects_from_event_object(
                event_object) + self.get_options_from_object(event_object)

    def get_templates_list(self, filtering_object):
        if filtering_object.__name__ == 'contract.option':
            return filtering_object.covered_element.product.report_templates
        return super(EventTypeAction, self).get_templates_list(
            filtering_object)


class EventLog:
    __metaclass__ = PoolMeta
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        if (model_name == 'contract' and
                object_.__name__ == 'contract.covered_element'):
            return [object_.main_contract]
        return super(EventLog, cls).get_related_instances(object_,
            model_name)
