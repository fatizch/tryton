# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import company
import res
import ir
import test_case
import party


def register():
    Pool.register(
        company.Company,
        res.User,
        res.Employee,
        ir.Sequence,
        ir.SequenceStrict,
        test_case.TestCaseModel,
        party.PartyConfiguration,
        module='company_cog', type_='model')
