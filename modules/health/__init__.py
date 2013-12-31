from trytond.pool import Pool

from .product import *
from .party import *
from .contract import *


def register():
    Pool.register(
        Product,
        Coverage,
        Party,
        HealthPartyComplement,
        Contract,
        Option,
        CoveredElement,
        module='health', type_='model')
