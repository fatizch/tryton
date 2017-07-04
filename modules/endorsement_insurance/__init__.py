# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import endorsement
import offered
import wizard


def register():
    Pool.register(
        endorsement.ContractOptionVersion,
        endorsement.CoveredElement,
        endorsement.CoveredElementVersion,
        endorsement.ExtraPremium,
        endorsement.OptionExclusionRelation,
        endorsement.Endorsement,
        endorsement.EndorsementContract,
        endorsement.EndorsementCoveredElement,
        endorsement.EndorsementCoveredElementVersion,
        offered.EndorsementCoveredElementVersionField,
        endorsement.EndorsementCoveredElementOption,
        offered.EndorsementCoveredElementField,
        endorsement.EndorsementCoveredElementOptionVersion,
        endorsement.EndorsementExtraPremium,
        offered.EndorsementExtraPremiumField,
        endorsement.EndorsementExclusion,
        offered.EndorsementExclusionField,
        offered.EndorsementPart,
        wizard.NewCoveredElement,
        wizard.RemoveOptionSelector,
        wizard.RemoveOption,
        wizard.NewOptionOnCoveredElement,
        wizard.ModifyCoveredElement,
        wizard.CoveredElementDisplayer,
        wizard.ExtraPremiumDisplayer,
        wizard.ManageExtraPremium,
        wizard.ManageOptions,
        wizard.OptionDisplayer,
        wizard.OptionSelector,
        wizard.CoveredElementSelector,
        wizard.NewExtraPremium,
        wizard.VoidContract,
        wizard.ManageExclusions,
        wizard.ManageExclusionsOptionDisplayer,
        wizard.ManageExclusionsDisplayer,
        module='endorsement_insurance', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_insurance', type_='wizard')
