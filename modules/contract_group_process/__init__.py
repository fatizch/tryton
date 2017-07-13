# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import document
import process
import wizard


def register():
    Pool.register(
        process.ContractSubscribeFindProcess,
        wizard.ContractGroupSubscribeFindProcess,
        document.DocumentDescription,
        module='contract_group_process', type_='model')
    Pool.register(
        process.ContractSubscribe,
        wizard.ContractGroupSubscribe,
        document.ReceiveDocument,
        module='contract_group_process', type_='wizard')
