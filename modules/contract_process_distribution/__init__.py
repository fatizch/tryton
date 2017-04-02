# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .process import *


def register():
    Pool.register(
        ContractSubscribeFindProcess,
        module='contract_process_distribution', type_='model')
    Pool.register(
        ContractSubscribe,
        module='contract_process_distribution', type_='wizard')