# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .payment import *


def register():
    Pool.register(
        Payment,
        Journal,
        module='account_payment_clearing_waiting', type_='model')
