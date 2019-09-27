# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from . import configuration
from . import offered

from . import api


def register():
    Pool.register(
        party.Party,
        configuration.Configuration,
        module='party_ssn', type_='model')

    Pool.register(
        api.APICore,
        api.APIParty,
        api.APIProduct,
        module='party_ssn', type_='model', depends=['api'])

    Pool.register(
        offered.ItemDescription,
        module='party_ssn', type_='model', depends=['offered_insurance'])
