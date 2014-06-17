from trytond.pool import Pool
from .clause import *
from .test_case import *


def register():
    Pool.register(
        Clause,
        TestCaseModel,
        module='clause', type_='model')
