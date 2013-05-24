from trytond.pool import Pool

from .distribution import *


def register():
    Pool.register(
        DistributionNetwork,
        module='distribution', type_='model')
