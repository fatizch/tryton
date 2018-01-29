# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from trytond.modules.insurer_reporting.batch import InsurerReportContractBatch


__all__ = [
    'InsurerReportClaimBatch',
    ]


class InsurerReportClaimBatch(InsurerReportContractBatch):
    'Insurer Report Claim Batch'

    __name__ = 'insurer_reporting.claim.generate'

    @classmethod
    def get_reporting_wizard(cls):
        InsurerReportWizard = Pool().get('claim_reporting.claim', type='wizard')
        wizard_id, _, _ = InsurerReportWizard.create()
        return InsurerReportWizard(wizard_id)

    @classmethod
    def get_insurers(cls):
        return Pool().get('insurer').search(
            [('claim_stock_reports', '!=', None)])

    @classmethod
    def get_templates_to_print(cls, objects):
        return [tmpl for insurer in objects
            for tmpl in insurer.claim_stock_reports
            if tmpl.kind == 'claim_insurer_report']
