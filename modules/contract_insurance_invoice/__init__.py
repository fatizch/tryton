from trytond.pool import Pool

from .invoice import *
from .offered import *
from .contract import *


def register():
    Pool.register(
        InvoiceFrequency,
        Product,
        ProductInvoiceFrequencyRelation,
        ProductPaymentTermRelation,
        OptionDescription,
        Invoice,
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
        FeeDesc,
        TaxDesc,
        InvoiceContractStart,
        CreateInvoiceContractBatch,
        PostInvoiceContractBatch,
        PaymentTerm,
        PaymentTermLine,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        module='contract_insurance_invoice', type_='wizard')
