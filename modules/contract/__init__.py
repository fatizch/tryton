from trytond.pool import Pool

from .contract import *


def register():
    Pool.register(
        Contract,
        SubscribedCoverage,
        module='contract', type_='model')
