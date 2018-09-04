# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import Pool
from trytond.wizard import StateView, Button
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields

__all__ = [
    'InsurerReportContractConfigure',
    'InsurerReportResult',
    'InsurerReportContract',
    ]


class InsurerReportContractConfigure(model.CoogView):
    'Configure Insurer Contract Reporting'

    __name__ = 'insurer_reporting.contract.configure'

    insurer = fields.Many2One('insurer', 'Insurer', required=True)
    template = fields.Many2One('report.template', 'Template', required=True,
        domain=[('kind', 'in', ('insurer_report_contract',
                    'insurer_report_covered'))])
    at_date = fields.Date('Date', required=True)


class InsurerReportResult(model.CoogView):
    'Insurer Reporting Result'

    __name__ = 'insurer_reporting.result'

    reports = fields.One2Many('ir.attachment', None, 'Reports', readonly=True)


class InsurerReportContract(model.CoogWizard):
    'Insurer Contract Reporting'

    __name__ = 'insurer_reporting.contract'

    start_state = 'configure_report'

    configure_report = StateView('insurer_reporting.contract.configure',
        'insurer_reporting.configure_insurer_contract_reporting_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Report', 'result', 'tryton-go-next')])
    result = StateView('insurer_reporting.result',
        'insurer_reporting.insurer_reporting_result_view_form', [
            Button('Ok', 'end', 'tryton-ok')])

    def default_result(self, name):
        pool = Pool()
        Contract = pool.get('contract')
        insurer = self.configure_report.insurer
        max_date = datetime.datetime.combine(self.configure_report.at_date,
            datetime.datetime.max.time())
        all_contracts = Contract.search([
                ('create_date', '<=', max_date),
                ('status', 'not in', ('quote', 'declined')),
                ['OR',
                    ('covered_elements.options.coverage.insurer', '=',
                        insurer),
                    ('options.coverage.insurer', '=', insurer)]])
        template = self.configure_report.template
        if not all_contracts:
            return {
                'reports': [],
                }
        with Transaction().set_context(
                reporting_date=max_date):
            _, attachments = template.produce_reports(all_contracts,
                {'origin': insurer, 'resource': insurer,
                    'reporting_date': max_date})
        return {
            'reports': [x.id for x in attachments],
            }
