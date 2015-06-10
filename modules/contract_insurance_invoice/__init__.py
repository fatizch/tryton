from trytond.pool import Pool

from .batch import *
from .invoice import *
from .party import *
from .offered import *
from .contract import *
from .account import *
from .wizard import *


def register():
    Pool.register(
        BillingMode,
        ProductBillingModeRelation,
        Product,
        BillingModePaymentTermRelation,
        OptionDescription,
        OptionDescriptionPremiumRule,
        Invoice,
        InvoiceLine,
        Configuration,
        Fee,
        Contract,
        ContractFee,
        ContractOption,
        ExtraPremium,
        ContractBillingInformation,
        Premium,
        ContractInvoice,
        MoveLine,
        InvoiceLineDetail,
        FeeDesc,
        TaxDesc,
        InvoiceContractStart,
        CreateInvoiceContractBatch,
        PostInvoiceContractBatch,
        PaymentTerm,
        PaymentTermLine,
        PaymentTermLineRelativeDelta,
        SynthesisMenuInvoice,
        SynthesisMenu,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        SynthesisMenuOpen,
        DisplayContractPremium,
        ContractBalance,
        Renew,
        module='contract_insurance_invoice', type_='wizard')
