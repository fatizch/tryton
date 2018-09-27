# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import party
import pasrau
import tax
import wizard
import batch


def register():
    Pool.register(
        claim.Indemnification,
        party.Party,
        pasrau.PartyCustomPasrauRate,
        pasrau.DefaultPasrauRate,
        tax.Invoice,
        tax.InvoiceLine,
        tax.Tax,
        wizard.ClaimPasrauSelectFile,
        batch.UpdatePartyPasrauRateBatch,
        module='claim_pasrau', type_='model')
    Pool.register(
        wizard.ClaimPasrauUploadWizard,
        module='claim_pasrau', type_='wizard')
