# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import contract
import offered
import extra_data
import report_engine
import rule_engine
from trytond.pool import Pool


def register():
    Pool.register(
        offered.UnderwritingDecision,
        offered.UnderwritingDecisionUnderwritingDecision,
        contract.Contract,
        contract.ContractUnderwriting,
        contract.ContractUnderwritingOption,
        offered.Product,
        offered.OptionDescription,
        extra_data.ExtraData,
        report_engine.ReportTemplate,
        offered.UnderwritingRule,
        offered.UnderwritingRuleUnderwritingDecision,
        rule_engine.RuleEngine,
        module='contract_underwriting', type_='model')
