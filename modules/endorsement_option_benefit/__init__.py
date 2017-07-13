# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import benefit
import endorsement
import wizard


def register():
    Pool.register(
        benefit.OptionBenefit,
        wizard.OptionDisplayer,
        wizard.ManageOptionBenefits,
        wizard.ManageOptionBenefitsDisplayer,
        endorsement.EndorsementContract,
        endorsement.EndorsementPart,
        endorsement.EndorsementBenefitField,
        endorsement.EndorsementOptionBenefit,
        endorsement.EndorsementOptionVersion,
        module='endorsement_option_benefit', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_option_benefit', type_='wizard')
