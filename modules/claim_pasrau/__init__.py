# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import claim
from . import party
from . import pasrau
from . import tax
from . import wizard
from . import batch
from . import slip
from . import message


def register():
    Pool.register(
        claim.Indemnification,
        party.Party,
        pasrau.PartyCustomPasrauRate,
        pasrau.DefaultPasrauRate,
        pasrau.MoveLinePasrauRate,
        tax.Invoice,
        tax.Tax,
        tax.MoveLine,
        tax.InvoiceTax,
        tax.InvoiceLineTax,
        batch.UpdatePartyPasrauRateBatch,
        slip.InvoiceSlipConfiguration,
        slip.Invoice,
        message.DsnMessage,
        wizard.ClaimPasrauSelectFile,
        wizard.InvoiceSlipParameters,
        wizard.ClaimPasrauImportFileSummary,
        module='claim_pasrau', type_='model')
    Pool.register(
        wizard.ClaimPasrauUploadWizard,
        module='claim_pasrau', type_='wizard')
