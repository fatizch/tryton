# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import batch
from .party import *
from .payment import *
from .company import *
from .move import *
from .report import *
from .invoice import *


def register():
    Pool.register(
        Journal,
        RejectReason,
        JournalFailureAction,
        Payment,
        MergedPayments,
        PaymentMotive,
        SynthesisMenuPayment,
        SynthesisMenu,
        Company,
        Move,
        MoveLine,
        PaymentInformationSelection,
        PaymentFailInformation,
        batch.PaymentTreatmentBatch,
        batch.PaymentCreationBatch,
        batch.PaymentSucceedBatch,
        batch.PaymentAcknowledgeBatch,
        Configuration,
        Group,
        Party,
        PaymentCreationStart,
        ReportTemplate,
        Invoice,
        module='account_payment_cog', type_='model')
    Pool.register(
        SynthesisMenuOpen,
        PaymentInformationModification,
        PaymentCreation,
        FilterPaymentsPerMergedId,
        ManualPaymentFail,
        ProcessManualFailPament,
        module='account_payment_cog', type_='wizard')
