from trytond.pool import Pool
from .statement import *
from .test_case import *
from .journal import *
from .move import *


def register():
    Pool.register(
        Line,
        Statement,
        TestCaseModel,
        Journal,
        Move,
        MoveLine,
        module='account_statement_cog', type_='model')
