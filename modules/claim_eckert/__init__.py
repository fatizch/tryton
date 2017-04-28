# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import benefit
import claim
import configuration
import document
import wizard


def register():
    Pool.register(
        claim.Claim,
        claim.ClaimBeneficiary,
        claim.Service,
        benefit.Benefit,
        document.DocumentRequestLine,
        configuration.ClaimConfiguration,
        wizard.IndemnificationDefinition,
        module='claim_eckert', type_='model')
