# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta, Pool


__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    def get_templates_list(self, filtering_object):
        if filtering_object.__name__ == 'account.invoice':
            return Pool().get('report.template').search([
                    [('on_model.model', '=', 'account.invoice')],
                    ['OR',
                        [('kind', '=', filtering_object.business_kind)],
                        [('kind', '=', '')],
                        ],
                    ])
        return super(EventTypeAction, self).get_templates_list(
            filtering_object)

    @classmethod
    def get_invoices_from_objects(cls, event_object):
        if event_object.__name__ == 'account.invoice':
            return [event_object]
        return []

    def get_filtering_objects_from_event_object(self, event_object):
        return super(
            EventTypeAction, self).get_filtering_objects_from_event_object(
                event_object) + self.get_invoices_from_objects(
                    event_object)
