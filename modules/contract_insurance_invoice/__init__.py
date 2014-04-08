from trytond.pool import Pool

from .invoice import *
from .contract import *


def register():
    Pool.register(
        InvoiceLine,
        Contract,
        ContractPaymentTerm,
        ContractInvoiceFrequency,
        ContractInvoice,
        ContractOption,
        CoveredElement,
        ExtraPremium,
        Premium,
        PremiumTax,
        InvoiceContractStart,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        module='contract_insurance_invoice', type_='wizard')
