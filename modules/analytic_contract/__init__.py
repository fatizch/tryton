# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import rule
from . import line


def register():
    Pool.register(
        rule.Rule,
        line.MoveLine,
        module='analytic_contract', type_='model')
