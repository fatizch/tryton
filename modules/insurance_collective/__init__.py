from trytond.pool import Pool
from .collective_product import *
from .collective_contract import *


def register():
    Pool.register(
        GroupProduct,
        GroupCoverage,
        GroupBenefit,
        GroupContract,
        module='insurance_collective', type_='model')
