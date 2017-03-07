# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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
from .bank import *
from .configuration import *
import payment


def register():
    Pool.register(
        BillingMode,
        BillingModeFeeRelation,
        ProductBillingModeRelation,
        Product,
        BillingModePaymentTermRelation,
        OptionDescription,
        OptionDescriptionPremiumRule,
        ContractInvoice,
        Invoice,
        InvoiceLine,
        Configuration,
        Fee,
        Contract,
        ContractSubStatus,
        ContractFee,
        ContractOption,
        ExtraPremium,
        ContractBillingInformation,
        Premium,
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
        BankAccount,
        OfferedConfiguration,
        payment.Payment,
        payment.PaymentSuspension,
        payment.JournalFailureAction,
        module='contract_insurance_invoice', type_='model')
    Pool.register(
        InvoiceContract,
        SynthesisMenuOpen,
        DisplayContractPremium,
        Reconcile,
        InvoiceLineAggregates,
        module='contract_insurance_invoice', type_='wizard')
