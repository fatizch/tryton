# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import batch


def register():
    Pool.register(
        batch.BankMobilityBatch,
        module='bank_mobility', type_='model')
