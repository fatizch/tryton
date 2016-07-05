# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .contract import *
from .offered import *
from .invoice import *
from .future_payments import *


def register():
    Pool.register(
        Contract,
        ExtraPremium,
        Premium,
        OptionDescriptionPremiumRule,
        OptionDescription,
        ProductPremiumDate,
        Product,
        InvoiceLineDetail,
        InvoiceLine,
        ShowAllInvoicesMain,
        ShowAllInvoicesLine,
        module='contract_loan_invoice', type_='model')

    Pool.register(
        ShowAllInvoices,
        module='contract_loan_invoice', type_='wizard')
