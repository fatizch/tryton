# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import contract
from . import offered
from . import batch


def register():
    Pool.register(
        offered.ItemDescription,
        contract.CoveredElement,
        batch.ContractNoemieFlowBatch,
        module='contract_noemie', type_='model')
