# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import company
from . import res
from . import ir
from . import test_case
from . import api


def register():
    Pool.register(
        company.Company,
        res.User,
        res.Employee,
        ir.Sequence,
        ir.SequenceStrict,
        ir.Date,
        test_case.TestCaseModel,
        module='company_cog', type_='model')

    Pool.register(
        api.APIModel,
        module='company_cog', type_='model', depends=['api'])
