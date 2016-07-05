# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .wizard import *
from .report_engine import *
from .account import *


def register():
    Pool.register(
        InsurerReportContractConfigure,
        InsurerReportResult,
        ReportTemplate,
        Invoice,
        InvoiceLine,
        module='insurer_reporting', type_='model')
    Pool.register(
        InsurerReportContract,
        module='insurer_reporting', type_='wizard')
