from trytond.pool import Pool
from .wizard import *


def register():
    Pool.register(
        ContractSubscribeFindProcess,
        module='insurance_collective_subscription', type_='model')
    Pool.register(
        ContractSubscribe,
        module='insurance_collective_subscription', type_='wizard')
