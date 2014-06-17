from trytond.pool import Pool

from .process import *
from .contract import *


def register():
    Pool.register(
        Contract,
        ContractOption,
        Process,
        ContractSubscribeFindProcess,
        module='contract_insurance_process', type_='model')

    Pool.register(
        ContractSubscribe,
        module='contract_insurance_process', type_='wizard')
