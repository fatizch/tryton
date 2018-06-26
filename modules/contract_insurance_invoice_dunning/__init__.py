# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import payment
import dunning
import offered
import contract
import account
import event
import invoice
import batch


def register():
    Pool.register(
        dunning.Dunning,
        dunning.Procedure,
        dunning.Level,
        contract.Contract,
        offered.Product,
        account.MoveLine,
        invoice.Invoice,
        payment.Payment,
        batch.DunningTreatmentBatch,
        batch.DunningCreationBatch,
        module='contract_insurance_invoice_dunning', type_='model')
    Pool.register(
        event.EventLog,
        event.EventTypeAction,
        module='contract_insurance_invoice_dunning', type_='model',
        depends=['event_log'])
