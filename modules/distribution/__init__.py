from trytond.pool import Pool

from .distribution import *
from .res import *
from .test_case import *


def register():
    Pool.register(
        # from distribution
        # DistributionNetwork,
        # # from res
        # User,
        # # from test_case
        # TestCaseModel,
        module='distribution', type_='model')
