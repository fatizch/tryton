from trytond.pool import Pool
from .life_contract_collective import *


def register():
    Pool.register(
        GroupCoveredElement,
        module='life_contract_collective', type_='model')
