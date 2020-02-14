# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import contract
from . import offered
from . import rule_engine


def register():
    Pool.register(
        contract.Contract,
        contract.ContractExtraDataRevision,
        offered.Product,
        offered.ProductExtraDetails,
        rule_engine.RuleEngine,
        rule_engine.Runtime,
        module='contract_extra_details', type_='model')
