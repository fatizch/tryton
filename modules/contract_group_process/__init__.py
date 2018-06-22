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
        wizard.ImportProcessSelect,
        module='contract_group_process', type_='model')
    Pool.register(
        process.ContractSubscribe,
        wizard.ContractGroupSubscribe,
        module='contract_group_process', type_='wizard')
    Pool.register(
        document.ReceiveDocument,
        module='contract_group_process', type_='wizard',
        depends=['document'])
    Pool.register(
        document.DocumentDescription,
        module='contract_group_process', type_='model',
        depends=['document'])

