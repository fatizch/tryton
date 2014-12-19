from trytond.pool import Pool

from .contract import *


def register():
    Pool.register(
        ContractSet,
        module='contract_set_invoice_report', type_='model')
