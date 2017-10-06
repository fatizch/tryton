# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import contract
import offered
import invoice
import future_payments


def register():
    Pool.register(
        contract.Contract,
        contract.ExtraPremium,
        contract.Premium,
        offered.OptionDescriptionPremiumRule,
        offered.OptionDescription,
        offered.ProductPremiumDate,
        offered.Product,
        invoice.InvoiceLineDetail,
        invoice.InvoiceLine,
        future_payments.ShowAllInvoicesMain,
        future_payments.ShowAllInvoicesLine,
        module='contract_loan_invoice', type_='model')

    Pool.register(
        future_payments.ShowAllInvoices,
        module='contract_loan_invoice', type_='wizard')
