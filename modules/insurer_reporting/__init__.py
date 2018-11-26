# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import wizard
from . import report_engine
from . import account
from . import contract
from . import party
from . import batch


def register():
    Pool.register(
        wizard.InsurerReportContractConfigure,
        wizard.InsurerReportResult,
        report_engine.ReportTemplate,
        account.Invoice,
        contract.Contract,
        contract.CoveredElement,
        party.InsurerReportTemplate,
        party.Insurer,
        batch.InsurerReportContractBatch,
        module='insurer_reporting', type_='model')
    Pool.register(
        wizard.InsurerReportContract,
        module='insurer_reporting', type_='wizard')
