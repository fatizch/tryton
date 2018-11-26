# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import claim
from . import contract
from . import endorsement


def register():
    Pool.register(
        claim.Benefit,
        claim.BenefitUnderwritingRule,
        contract.OptionBenefit,
        module='underwriting_claim_group', type_='model')
    Pool.register(
        endorsement.ManageOptionBenefits,
        endorsement.ManageOptionBenefitsDisplayer,
        module='underwriting_claim_group', type_='model',
        depends=['endorsement_option_benefit'])
