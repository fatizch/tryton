# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .dunning import *
from .report_engine import *


def register():
    Pool.register(
        ReportTemplate,
        Dunning,
        Level,
        module='account_dunning_report_engine', type_='model')
