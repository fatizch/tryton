from trytond.pool import Pool
from .contract import *
from .benefit import *


def register():
    Pool.register(
        ContractService,
        BenefitRule,
        module='claim_credit', type_='model')
