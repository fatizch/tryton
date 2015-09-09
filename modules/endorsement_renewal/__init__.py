from trytond.pool import Pool
from .wizard import *
from .contract import *


def register():
    Pool.register(
        ContractRenew,
        Contract,
        module='endorsement_renewal', type_='model')
    Pool.register(
        StartEndorsement,
        module='endorsement_renewal', type_='wizard')
