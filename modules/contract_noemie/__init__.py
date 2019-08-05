# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import contract
from . import contract_endorsement
from . import offered


def register():
    Pool.register(
        offered.ItemDescription,
        contract.Contract,
        contract.CoveredElement,
        batch.ContractNoemieFlowBatch,
        module='contract_noemie', type_='model')

    Pool.register(
        contract_endorsement.Contract,
        module='contract_noemie', type_='model',
        depends=['endorsement_insurance'])
