from trytond.pool import Pool
from .statement import *


def register():
    Pool.register(
        Line,
        Statement,
        module='account_statement_contract_fr', type_='model')
