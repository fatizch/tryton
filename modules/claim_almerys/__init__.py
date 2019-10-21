# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import claim
from . import account
from . import offered
from . import test_case


def register():
    Pool.register(
        batch.AlmerysClaimIndemnification,
        batch.AlmerysStatementCreation,
        claim.Claim,
        claim.AlmerysConfig,
        claim.Service,
        claim.Benefit,
        claim.Loss,
        claim.HealthLoss,
        account.Invoice,
        account.InvoiceLine,
        offered.OptionDescription,
        test_case.TestCaseModel,
        test_case.TestCaseAlmerysInsurer,
        batch.AlmerysPaybackCreation,
        module='claim_almerys', type_='model')
