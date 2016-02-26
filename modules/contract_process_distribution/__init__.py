from trytond.pool import Pool

from .process import *


def register():
    Pool.register(
        ContractSubscribeFindProcess,
        module='contract_process_distribution', type_='model')
    Pool.register(
        ContractSubscribe,
        module='contract_process_distribution', type_='wizard')
