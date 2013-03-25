from trytond.pool import Pool
from .collective_subscription_process import *


def register():
    Pool.register(
        GroupSubscriptionProcessParameters,
        module='insurance_collective_subscription', type_='model')
    Pool.register(
        SubscriptionProcessFinder,
        module='insurance_collective_subscription', type_='wizard')
