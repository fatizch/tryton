from trytond.pool import Pool
from .bank import *
from .test_case import *


def register():
    Pool.register(
        Bank,
        Agency,
        TestCaseModel,
        module='bank_fr', type_='model')
