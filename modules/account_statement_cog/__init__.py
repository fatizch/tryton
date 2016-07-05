# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .statement import *
from .test_case import *
from .journal import *
from .move import *


def register():
    Pool.register(
        Line,
        Statement,
        LineGroup,
        TestCaseModel,
        Journal,
        Move,
        MoveLine,
        CancelLineGroupStart,
        CancelMotive,
        JournalCancelMotiveRelation,
        module='account_statement_cog', type_='model')
    Pool.register(
        CancelLineGroup,
        module='account_statement_cog', type_='wizard')
