from trytond.pool import Pool

from .tax import *


def register():
    Pool.register(
        # from tax
        TaxDesc,
        TaxVersion,
        TaxManager,
        ManagerTaxRelation,
        module='coop_account', type_='model')
