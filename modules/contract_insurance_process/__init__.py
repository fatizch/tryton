# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import process
import contract
import event
import document
import wizard


def register():
    Pool.register(
        contract.Contract,
        contract.ContractOption,
        contract.ContractNotification,
        process.Process,
        process.ProcessAction,
        process.ContractSubscribeFindProcess,
        event.EventTypeAction,
        document.DocumentDescription,
        wizard.ImportProcessSelect,
        module='contract_insurance_process', type_='model')

    Pool.register(
        process.ContractSubscribe,
        document.ReceiveDocument,
        process.ProcessResume,
        module='contract_insurance_process', type_='wizard')
