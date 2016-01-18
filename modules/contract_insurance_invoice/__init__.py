from trytond.pool import Pool

from .batch import *
from .invoice import *
from .party import *
from .offered import *
from .contract import *
from .account import *
from .move import *
from .rule_engine import *
from .event import *


def register():
    Pool.register(
        BillingMode,
        BillingModeFeeRelation,
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
        ReconcileShow,
        InvoiceLineDetail,
        InvoiceLineAggregatesDisplay,
        InvoiceLineAggregatesDisplayLine,
        InvoiceContractStart,
        CreateInvoiceContractBatch,
        PostInvoiceContractBatch,
        SetNumberInvoiceContractBatch,
        PaymentTerm,
        PaymentTermLine,
        PaymentTermLineRelativeDelta,
        SynthesisMenuInvoice,
        SynthesisMenu,
        RuleEngineRuntime,
        Event,
        EventLog,
        EventTypeAction,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        SynthesisMenuOpen,
        DisplayContractPremium,
        Reconcile,
        InvoiceLineAggregates,
        module='contract_insurance_invoice', type_='wizard')
