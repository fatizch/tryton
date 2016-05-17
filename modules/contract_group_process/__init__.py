from trytond.pool import Pool
from .wizard import *
from .process import *

def register():
    Pool.register(
        ContractSubscribeFindProcess,
        ContractGroupSubscribeFindProcess,
        module='contract_group_process', type_='model')
    Pool.register(
        ContractSubscribe,
        ContractGroupSubscribe,
        module='contract_group_process', type_='wizard')
