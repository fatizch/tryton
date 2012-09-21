from trytond.pool import Pool

from .tax import *
from .fee import *


def register():
    Pool.register(
        # from tax
        TaxDesc,
        TaxVersion,
        # from fee
        FeeDesc,
        FeeVersion,
        module='coop_account', type_='model')
