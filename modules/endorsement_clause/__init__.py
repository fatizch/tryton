# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import offered
import endorsement
import wizard


def register():
    Pool.register(
        offered.EndorsementPart,
        offered.EndorsementClauseField,
        endorsement.Clause,
        endorsement.EndorsementContract,
        endorsement.EndorsementClause,
        wizard.ManageClauses,
        wizard.ClauseDisplayer,
        module='endorsement_clause', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_clause', type_='wizard')
