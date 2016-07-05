# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .statement import *


def register():
    Pool.register(
        Line,
        Statement,
        module='account_statement_contract_fr', type_='model')
