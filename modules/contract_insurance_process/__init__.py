# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .process import *
from .contract import *
from .event import *
from .document import *


def register():
    Pool.register(
        Contract,
        ContractOption,
        Process,
        ContractSubscribeFindProcess,
        EventTypeAction,
        DocumentDescription,
        module='contract_insurance_process', type_='model')

    Pool.register(
        ContractSubscribe,
        ReceiveDocument,
        module='contract_insurance_process', type_='wizard')
