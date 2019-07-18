# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import process
from . import contract
from . import event
from . import document
from . import wizard
from . import offered
from . import api


def register():
    Pool.register(
        contract.Contract,
        contract.ContractOption,
        contract.ContractNotification,
        process.ProcessProductRelation,
        process.Process,
        process.ProcessAction,
        process.ContractSubscribeFindProcess,
        offered.Product,
        event.EventTypeAction,
        document.DocumentDescription,
        wizard.ImportProcessSelect,
        module='contract_process', type_='model')

    Pool.register(
        process.ContractSubscribe,
        document.ReceiveDocument,
        process.ProcessResume,
        module='contract_process', type_='wizard')

    Pool.register(
        api.APIContract,
        module='contract_process', type_='model', depends=['api'])
