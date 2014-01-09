from trytond.pool import Pool
from .wizard import *


def register():
    Pool.register(
        ContractSubscribeFindProcess,
        module='contract_group_process', type_='model')
    Pool.register(
        ContractSubscribe,
        module='contract_group_process', type_='wizard')
