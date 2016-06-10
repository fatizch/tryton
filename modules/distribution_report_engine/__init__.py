from trytond.pool import Pool

from report_engine import *
from offered import *
from contract import *
from event import *


def register():
    Pool.register(
        CommercialProduct,
        ReportComProductRelation,
        ReportTemplate,
        Contract,
        EventTypeAction,
        module='distribution_report_engine', type_='model')
