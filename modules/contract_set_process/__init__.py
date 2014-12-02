from trytond.pool import Pool

from .process import *
from .contract import *


def register():
    Pool.register(
        ContractSet,
        Process,
        ContractSetValidateFindProcess,
        module='contract_set_process', type_='model')

    Pool.register(
        ContractSetValidate,
        module='contract_set_process', type_='wizard')
