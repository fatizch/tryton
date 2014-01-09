from trytond.pool import Pool
from .offered import *
from .contract import *
from .benefit import *


def register():
    Pool.register(
        # From Offered
        Product,
        OptionDescription,
        # From Benefit
        Benefit,
        # From Contract
        Contract,
        module='contract_group', type_='model')
