from trytond.pool import Pool

from .distribution import *
from .res import *

def register():
    Pool.register(
        DistributionNetwork,
        User,
        module='distribution', type_='model')
