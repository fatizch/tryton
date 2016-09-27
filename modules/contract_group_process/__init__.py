# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .wizard import *
from .process import *
from .document import *


def register():
    Pool.register(
        ContractSubscribeFindProcess,
        ContractGroupSubscribeFindProcess,
        DocumentDescription,
        module='contract_group_process', type_='model')
    Pool.register(
        ContractSubscribe,
        ContractGroupSubscribe,
        ReceiveDocument,
        module='contract_group_process', type_='wizard')
