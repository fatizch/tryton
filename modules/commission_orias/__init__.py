# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from . import api


def register():
    Pool.register(
        party.Party,
        party.PartyIdentifier,
        module='commission_orias', type_='model')

    Pool.register(
        api.APICore,
        module='commission_orias', type_='model', depends=['api'])
