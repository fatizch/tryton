# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import work_days


def register():
    Pool.register(
        work_days.Configuration,
        work_days.Holiday,
        work_days.BatchParamsConfig,
        module='work_days', type_='model')
