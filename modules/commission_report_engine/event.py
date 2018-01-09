# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields
from trytond.pyson import Eval, And


__all__ = [
    'EventTypeAction',
    ]


class EventTypeAction:
    __metaclass__ = PoolMeta
    __name__ = 'event.type.action'

    @classmethod
    def __setup__(cls):
        super(EventTypeAction, cls).__setup__()
        cls._error_messages.update({
                'generate_invoice_commission_doc':
                'Generate Invoice Commissions Document',
                })
        initial_invisible_states = cls.report_templates.states['invisible']
        cls.report_templates.states['invisible'] = And(
            initial_invisible_states,
            Eval('action') != 'generate_invoice_commission_doc')

    @classmethod
    def possible_asynchronous_actions(cls):
        return super(EventTypeAction, cls).possible_asynchronous_actions() + \
            ['generate_invoice_commission_doc']

    @classmethod
    def get_action_types(cls):
        return super(EventTypeAction, cls).get_action_types() + [
            ('generate_invoice_commission_doc', cls.raise_user_error(
                    'generate_invoice_commission_doc', raise_exception=False))]

    @fields.depends('report_templates')
    def on_change_action(self):
        super(EventTypeAction, self).on_change_action()
        if self.action == 'generate_invoice_commission_doc':
            self.report_templates = \
                self.get_possible_commission_report_templates()

    def get_possible_commission_report_templates(cls):
        pool = Pool()
        model_id = pool.get('invoice.report.definition').get_on_model()
        return [x.id for x in pool.get('report.template').search(
            [('on_model', '=', model_id)])]

    def get_templates_list(self, filtering_object):
        if filtering_object.__name__ == 'account.invoice':
            ReportInvoiceDef = Pool().get('invoice.report.definition')
            definitions = ReportInvoiceDef.get_invoice_report_definition(
                parties=None, report_templates=None,
                business_kinds=[filtering_object.business_kind])
            if not definitions:
                return super(EventTypeAction, self).get_templates_list(
                    filtering_object)
            return [x.report_template for x in definitions
                if not x.party or x.party == filtering_object.party]
        return super(EventTypeAction, self).get_templates_list(filtering_object)

    def execute(self, objects, event_code, description=None, **kwargs):
        if self.action != 'generate_invoice_commission_doc':
            return super(EventTypeAction, self).execute(objects, event_code,
                description, **kwargs)
        self.action_generate_documents(objects, event_code, description,
            **kwargs)
