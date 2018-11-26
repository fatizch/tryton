# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import report_engine
from . import offered
from . import contract
from . import event


def register():
    Pool.register(
        offered.CommercialProduct,
        report_engine.ReportComProductRelation,
        report_engine.ReportTemplate,
        contract.Contract,
        event.EventTypeAction,
        module='distribution_report_engine', type_='model')
