# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model


__all__ = [
    'InvoiceReportDefinition',
    ]


class InvoiceReportDefinition(model.CoogSQL, model.CoogView):
    'Invoice Report Configuration'

    __name__ = 'invoice.report.definition'

    party = fields.Many2One('party.party', 'Party', select=True,
        ondelete='CASCADE')
    on_model = fields.Function(fields.Many2One('ir.model', 'Model'),
        'get_on_model')
    report_template = fields.Many2One('report.template', 'Report Template',
        domain=[('on_model', '=', Eval('on_model'))], depends=['on_model'],
        required=True, select=True, ondelete='RESTRICT')
    business_kind = fields.Function(fields.Char('Business Kind'),
            'get_business_kind', searcher='search_business_kind')

    @classmethod
    def search_business_kind(cls, name, clause):
        return [('report_template.kind',) + clause[1:]]

    @classmethod
    def get_invoice_report_definition(cls, parties=None, report_templates=None,
            business_kinds=None):
        clause = []
        parties = (x.id for x in parties) if parties else None
        templates = (x.id for x in report_templates) \
            if report_templates else None
        business_kinds = tuple(business_kinds)
        for fname, values in (('party', parties),
                ('report_template', templates),
                ('business_kind', business_kinds)):
            if values is not None:
                clause.append((fname, 'in', values))
        search_res = cls.search(clause)
        return search_res

    def get_business_kind(self, name=None):
        if self.report_template:
            return self.report_template.kind

    @classmethod
    def default_on_model(cls):
        return Pool().get('ir.model').search(
            [('model', '=', 'account.invoice')])[0].id

    @classmethod
    def get_on_model(cls, instances=None, name=None):
        model_id = Pool().get('ir.model').search(
            [('model', '=', 'account.invoice')])[0].id
        if instances is None:
            return model_id
        return {x.id: model_id for x in instances}
