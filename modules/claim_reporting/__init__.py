# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import wizard
import report_engine
import batch
import party


def register():
    Pool.register(
        wizard.InsurerReportClaimConfigure,
        wizard.InsurerReportClaimResult,
        report_engine.ReportTemplate,
        batch.InsurerReportClaimBatch,
        party.Insurer,
        module='claim_reporting', type_='model')
    Pool.register(
        wizard.InsurerReportClaim,
        module='claim_reporting', type_='wizard')
