from trytond.pool import Pool

from .contract import *


def register():
    Pool.register(
        StatusHistory,
        Contract,
        SubscribedCoverage,
        ContractAddress,
        module='contract', type_='model')
