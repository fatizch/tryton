# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import contract
import party
import provider
import token


def register():
    Pool.register(
        contract.Contract,
        provider.Provider,
        party.Party,
        token.Token,
        module='customers_provider_login', type_='model')
