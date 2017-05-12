# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .contract import *
from .account import *
from .wizard import *
from .dunning import *
from .move import *
from .payment import *


def register():
    Pool.register(
        Contract,
        ContractSet,
        Fee,
        Level,
        PartyBalance,
        Payment,
        module='contract_set_insurance_invoice', type_='model')
    Pool.register(
        DisplayContractSetPremium,
        Renew,
        module='contract_set_insurance_invoice', type_='wizard')
