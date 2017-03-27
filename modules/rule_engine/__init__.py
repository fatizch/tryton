# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from .batch import *
from .rule_engine import *
import view


def register():
    Pool.register(
        # From rule_engine
        RuleTools,
        Context,
        RuleEngine,
        RuleEngineTable,
        RuleEngineRuleEngine,
        RuleParameter,
        RuleExecutionLog,
        TestCase,
        TestCaseValue,
        RuleFunction,
        ContextRuleFunction,
        RuleEngineFunctionRelation,
        RunTestsReport,
        RuleError,
        ValidateRuleBatch,
        view.View,
        module='rule_engine', type_='model')
    Pool.register(
        # From rule_engine
        RunTests,
        ValidateRuleTestCases,
        InitTestCaseFromExecutionLog,
        module='rule_engine', type_='wizard')
