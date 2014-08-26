from trytond.pool import Pool

from .invoice import *
from .party import *
from .offered import *
from .contract import *
from .payment import *
from .move import *


def register():
    Pool.register(
        BillingMode,
        ProductBillingModeRelation,
        Product,
        BillingModePaymentTermRelation,
        OptionDescription,
        Invoice,
        InvoiceLine,
        Contract,
        ContractBillingInformation,
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
        PaymentCreationBatch,
        PaymentTreatmentBatch,
        Configuration,
        MoveLine,
        SynthesisMenuInvoice,
        SynthesisMenu,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        SynthesisMenuOpen,
        DisplayContractPremium,
        module='contract_insurance_invoice', type_='wizard')
