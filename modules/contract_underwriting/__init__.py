# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from . import contract
from . import offered
from . import extra_data
from . import report_engine
from . import rule_engine
from . import test_case
from trytond.pool import Pool


def register():
    Pool.register(
        offered.UnderwritingDecision,
        offered.UnderwritingDecisionUnderwritingDecision,
        contract.Contract,
        contract.ContractOption,
        contract.ContractUnderwriting,
        contract.ContractUnderwritingOption,
        contract.ContractExtraData,
        offered.Product,
        offered.OptionDescription,
        extra_data.ExtraData,
        report_engine.ReportTemplate,
        offered.UnderwritingRule,
        offered.UnderwritingRuleUnderwritingDecision,
        rule_engine.RuleEngine,
        test_case.TestCaseModel,
        module='contract_underwriting', type_='model')
