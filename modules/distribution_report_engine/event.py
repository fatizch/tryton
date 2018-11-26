# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction(metaclass=PoolMeta):
    __name__ = 'event.type.action'

    def get_templates_list(self, filtering_object):
        templates = list(super(EventTypeAction, self).get_templates_list(
                filtering_object))
        if filtering_object.__name__ == 'contract':
            if filtering_object.com_product and \
                    filtering_object.com_product.report_templates:
                templates.extend(filtering_object.com_product.report_templates)
        return templates
