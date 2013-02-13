from trytond.pool import Pool
from .loan_product import *
from .loan_rule_sets import *


def register():
    Pool.register(
        LoanProduct,
        LoanCoverage,
        LoanContext,
        module='loan_product', type_='model')
