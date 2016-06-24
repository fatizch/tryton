from trytond.pool import Pool

from .batch import *
from .rule_engine import *


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
        module='rule_engine', type_='model')
    Pool.register(
        # From rule_engine
        RunTests,
        ValidateRuleTestCases,
        InitTestCaseFromExecutionLog,
        module='rule_engine', type_='wizard')
