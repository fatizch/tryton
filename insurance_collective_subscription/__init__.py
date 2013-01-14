from trytond.pool import Pool
from .subscription_process import *


def register():
    Pool.register(
        GroupContractSubscription,
        module='insurance_collective_subscription', type_='model')
