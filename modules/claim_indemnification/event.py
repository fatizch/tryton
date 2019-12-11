# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import utils

__all__ = [
    'EventLog',
    'EventTypeAction',
    ]


class EventTypeAction(metaclass=PoolMeta):
    __name__ = 'event.type.action'

    def get_templates_list(self, filtering_object):
        res = super(EventTypeAction, self).get_templates_list(
            filtering_object)
        if filtering_object.__name__ == 'account.invoice':
            return res + Pool().get('report.template').search(
                [('on_model.model', '=', 'claim')])
        return res

    def get_objects_for_process(self, objects, target_model_name):
        if target_model_name != 'claim':
            return super(EventTypeAction, self).get_objects_for_process(
                objects, target_model_name)
        process_objects = []
        for object_ in objects:
            process_objects.append(object_.service.claim)
        return process_objects

    def get_targets_and_origin_from_object_and_template(self, object_,
            template):
        if template.on_model and template.on_model.model == 'claim':
            if object_.__name__ == 'account.payment.group':
                invoices = {payment.related_invoice
                    for payment in object_.payments}
            elif object_.__name__ == 'account.invoice':
                invoices = [object_]
            claims = {claim_detail.claim
                for invoice in invoices
                for invoice_line in invoice.lines
                for claim_detail in invoice_line.claim_details}
            return list(claims), object_
        return super(EventTypeAction,
            self).get_targets_and_origin_from_object_and_template(object_,
                template)


class EventLog(metaclass=PoolMeta):
    __name__ = 'event.log'

    @classmethod
    def get_related_instances(cls, object_, model_name):
        # TODO: use claim details to calculate the contract
        if model_name == 'contract':
            if object_.__name__ == 'claim.indemnification':
                return [object_.service.contract]
            if (object_.__name__ == 'account.invoice' and
                    not hasattr(object_, 'contract')):
                return []
            if object_.__name__ == 'account.payment':
                # The module may not be installed, which would cause a crash
                if not utils.is_module_installed('contract_insurance_payment'):
                    return []
        return super(EventLog, cls).get_related_instances(object_, model_name)
