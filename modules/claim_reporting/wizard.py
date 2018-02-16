# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import Pool
from trytond.wizard import StateView, Button
from trytond.transaction import Transaction

from trytond.modules.coog_core import model, fields

__all__ = [
    'InsurerReportClaimConfigure',
    'InsurerReportClaimResult',
    'InsurerReportClaim',
    ]


class InsurerReportClaimConfigure(model.CoogView):
    'Configure Insurer Claim Reporting'

    __name__ = 'claim_reporting.claim.configure'

    insurer = fields.Many2One('insurer', 'Insurer', required=True)
    template = fields.Many2One('report.template', 'Template', required=True,
        domain=[('kind', 'in', ('claim_insurer_report', ))])
    at_date = fields.Date('Date', required=True)


class InsurerReportClaimResult(model.CoogView):
    'Insurer Claim Reporting Result'

    __name__ = 'claim_reporting.result'

    reports = fields.One2Many('ir.attachment', None, 'Reports', readonly=True)


class InsurerReportClaim(model.CoogWizard):
    'Insurer Claim Reporting'

    __name__ = 'claim_reporting.claim'

    start_state = 'configure_report'
    configure_report = StateView('claim_reporting.claim.configure',
        'claim_reporting.claim_reporting_configure_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Report', 'result', 'tryton-go-next')])
    result = StateView('claim_reporting.result',
        'claim_reporting.claim_reporting_result_view_form', [
            Button('Ok', 'end', 'tryton-ok')])

    def default_result(self, name):
        pool = Pool()
        ClaimService = pool.get('claim.service')
        insurer = self.configure_report.insurer
        max_date = datetime.datetime.combine(self.configure_report.at_date,
            datetime.datetime.max.time())
        all_services = ClaimService.search([
                ('create_date', '<=', max_date),
                ('option.coverage.insurer', '=', insurer)
                ])
        template = self.configure_report.template
        with Transaction().set_context(
                reporting_date=max_date):
            _, attachments = template.produce_reports(all_services,
                {'origin': insurer, 'resource': insurer,
                    'reporting_date': max_date})
        return {
            'reports': [x.id for x in attachments],
            }
