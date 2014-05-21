from trytond.pool import Pool

from .invoice import *
from .party import *
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
        DisplayContractPremiumDisplayer,
        DisplayContractPremiumDisplayerPremiumLine,
        CreateInvoiceContractBatch,
        PostInvoiceContractBatch,
        PaymentTerm,
        PaymentTermLine,
        SynthesisMenuInvoice,
        SynthesisMenu,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        SynthesisMenuOpen,
        DisplayContractPremium,
        module='contract_insurance_invoice', type_='wizard')
