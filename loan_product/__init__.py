from trytond.pool import Pool
from .loan_product import *


def register():
    Pool.register(
        LoanProduct,
        LoanCoverage,
        module='loan_product', type_='model')
