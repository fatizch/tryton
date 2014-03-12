from trytond.pool import Pool
from .company import *
from .ir import *
from .res import *
from .test_case import *


def register():
    Pool.register(
        # From company
        Company,
        # From ir
        Sequence,
        Property,
        # From res
        User,
        Employee,
        # From test_case
        TestCaseModel,
        module='company_cog', type_='model')
