from trytond.pool import Pool
from trytond.wizard import StateView, Button

from trytond.modules.cog_utils import model, fields

__all__ = [
    'InsurerReportContractConfigure',
    'InsurerReportResult',
    'InsurerReportContract',
    ]


class InsurerReportContractConfigure(model.CoopView):
    'Configure Insurer Contract Reporting'

    __name__ = 'insurer_reporting.contract.configure'

    insurer = fields.Many2One('insurer', 'Insurer', required=True)
    template = fields.Many2One('report.template', 'Template', required=True,
        domain=[('kind', 'in', ('insurer_report_contract',
                    'insurer_report_covered'))])


class InsurerReportResult(model.CoopView):
    'Insurer Reporting Result'

    __name__ = 'insurer_reporting.result'

    reports = fields.One2Many('ir.attachment', None, 'Reports', readonly=True)


class InsurerReportContract(model.CoopWizard):
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
        all_contracts = Contract.search([
                ('status', 'not in', ('quote', 'declined')),
                ['OR',
                    ('covered_elements.options.coverage.insurer', '=',
                        insurer),
                    ('options.coverage.insurer', '=', insurer)]])
        template = self.configure_report.template
        _, attachments = template.produce_reports(all_contracts,
            {'origin': insurer, 'resource': insurer})
        return {
            'reports': [x.id for x in attachments],
            }
