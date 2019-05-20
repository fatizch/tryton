# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import party


def register():
    Pool.register(
        party.Party,
        party.ThirdPartyManager,
        module='third_party_management', type_='model')
