from trytond.pool import Pool
from .collective_product import *
from .collective_contract import *


def register():
    Pool.register(
        GroupProduct,
        GroupCoverage,
        GroupContract,
        GroupCoveredData,
        module='insurance_collective', type_='model')
