# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import process
import contract


def register():
    Pool.register(
        contract.ContractSet,
        process.Process,
        process.ContractSetValidateFindProcess,
        module='contract_set_process', type_='model')

    Pool.register(
        process.ContractSetValidate,
        module='contract_set_process', type_='wizard')
