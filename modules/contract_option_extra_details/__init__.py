# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import rule_engine
import offered
import contract


def register():
    Pool.register(
        rule_engine.RuleEngine,
        rule_engine.Runtime,
        offered.Coverage,
        offered.CoverageExtraDetails,
        contract.Contract,
        contract.ContractOption,
        contract.ContractOptionVersion,
        module='contract_option_extra_details', type_='model')
