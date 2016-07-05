# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .offered import *
from .extra_data import *
from .report_engine import *
from .contract import *
from .rule_engine import *


def register():
    Pool.register(
        UnderwritingDecision,
        UnderwritingDecisionUnderwritingDecision,
        Contract,
        ContractUnderwriting,
        ContractUnderwritingOption,
        Product,
        OptionDescription,
        ExtraData,
        ReportTemplate,
        UnderwritingRule,
        UnderwritingRuleUnderwritingDecision,
        RuleEngine,
        module='contract_underwriting', type_='model')
