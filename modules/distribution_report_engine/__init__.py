from trytond.pool import Pool

from report_engine import *
from offered import *
from contract import *


def register():
    Pool.register(
        CommercialProduct,
        ReportComProductRelation,
        ReportTemplate,
        Contract,
        module='distribution_report_engine', type_='model')
