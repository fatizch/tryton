# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import offered
import contract
import invoice


def register():
    Pool.register(
        offered.Product,
        offered.OptionDescription,
        contract.Contract,
        contract.ContractDeposit,
        invoice.Invoice,
        invoice.InvoiceLine,
        module='contract_cash_value', type_='model')
