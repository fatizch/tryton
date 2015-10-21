from trytond.pool import Pool
from .company import *
from .res import *
from .test_case import *
from .ir import *


def register():
    Pool.register(
        Company,
        User,
        Employee,
        Sequence,
        TestCaseModel,
        module='company_cog', type_='model')
