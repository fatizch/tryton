from trytond.pool import Pool

from .process import *


def register():
    Pool.register(
        ContractSubscribe,
        module='contract_process_commission', type_='wizard')
