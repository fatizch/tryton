# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import configuration
import batch


def register():
    Pool.register(
        configuration.Configuration,
        batch.ContractDeclineInactiveQuotes,
        module='contract_inactive_quote_declination', type_='model')
