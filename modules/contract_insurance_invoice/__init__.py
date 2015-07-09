from trytond.pool import Pool

from .batch import *
from .invoice import *
from .party import *
from .offered import *
from .contract import *
from .account import *
from .wizard import *
from .move import *
from .rule_engine import *


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
        Move,
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
        RuleEngineRuntime,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        SynthesisMenuOpen,
        DisplayContractPremium,
        Renew,
        module='contract_insurance_invoice', type_='wizard')
