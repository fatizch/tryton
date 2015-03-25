from trytond.pool import Pool

from .batch import *
from .invoice import *
from .party import *
from .offered import *
from .contract import *
from .account import *


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
        SynthesisMenuInvoice,
        SynthesisMenu,
        ChangeBankAccountSelect,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        SynthesisMenuOpen,
        DisplayContractPremium,
        ContractBalance,
        ChangeBankAccount,
        module='contract_insurance_invoice', type_='wizard')
