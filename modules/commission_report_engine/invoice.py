# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta, Pool

__all__ = [
    'Invoice',
    ]


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    def get_doc_template_kind(self):
        ReportInvoiceDef = Pool().get('invoice.report.definition')
        definitions = ReportInvoiceDef.get_invoice_report_definition(
            parties=None, report_templates=None,
            business_kinds=[self.business_kind])
        if definitions:
            return list({x.business_kind for x in definitions
                    if (x.party == self.party or not x.party)})
        return super(Invoice, self).get_doc_template_kind()

    def get_available_doc_templates(self, kind=None):
        templates = super(Invoice, self).get_available_doc_templates(kind)
        ReportInvoiceDef = Pool().get('invoice.report.definition')
        definitions = ReportInvoiceDef.get_invoice_report_definition(
            report_templates=templates, business_kinds=[self.business_kind])
        if definitions:
            return [x.report_template for x in definitions
                if not x.party or x.party == self.party]
        return templates
