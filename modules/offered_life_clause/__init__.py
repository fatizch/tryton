# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import clause
import test_case
import offered


def register():
    Pool.register(
        offered.OptionDescription,
        clause.Clause,
        offered.OptionDescriptionBeneficiaryClauseRelation,
        test_case.TestCaseModel,
        module='offered_life_clause', type_='model')
