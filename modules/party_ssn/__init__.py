# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import party


def register():
    Pool.register(
        party.Party,
        module='party_ssn', type_='model')
