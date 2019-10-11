# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import rule_engine
from . import contract
from . import offered
from . import batch


def register():
    Pool.register(
        rule_engine.RuleEngine,
        offered.ProductBillingRule,
        contract.Contract,
        batch.CreateInvoiceContractBatch,
        module='contract_invoicing_duration', type_='model')