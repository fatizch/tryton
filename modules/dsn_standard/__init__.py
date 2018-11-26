# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import message


def register():
    Pool.register(
        message.DsnMessage,
        module='dsn_standard', type_='model')
