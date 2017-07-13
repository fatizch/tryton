# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import payment


def register():
    Pool.register(
        payment.MigratorPayment,
        module='migrator_payment', type_='model')
