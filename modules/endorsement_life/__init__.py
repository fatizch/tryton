# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import offered
from . import endorsement
from . import wizard


def register():
    Pool.register(
        offered.EndorsementPart,
        offered.EndorsementBeneficiaryField,
        endorsement.Beneficiary,
        endorsement.EndorsementContract,
        endorsement.EndorsementCoveredElementOption,
        endorsement.EndorsementBeneficiary,
        wizard.ManageBeneficiaries,
        wizard.ManageBeneficiariesOptionDisplayer,
        wizard.ManageBeneficiariesDisplayer,
        module='endorsement_life', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        wizard.PartyErase,
        module='endorsement_life', type_='wizard')

    Pool.register(
        wizard.ManageBeneficiariesOptionDisplayerPortfolio,
        module='endorsement_life', type_='model',
        depends=['distribution_portfolio'])
