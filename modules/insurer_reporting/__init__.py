# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import wizard
import report_engine
import account
import contract
import batch


def register():
    Pool.register(
        wizard.InsurerReportContractConfigure,
        wizard.InsurerReportResult,
        report_engine.ReportTemplate,
        account.Invoice,
        account.InvoiceLine,
        contract.Contract,
        contract.CoveredElement,
        batch.InsurerReportContractBatch,
        module='insurer_reporting', type_='model')
    Pool.register(
        wizard.InsurerReportContract,
        module='insurer_reporting', type_='wizard')
