from trytond.pool import Pool
from .rule_engine import *
from .tag import *


def register():
    Pool.register(
        # From tag
        Tag,
        # From rule_engine
        RuleTools,
        Context,
        Rule,
        RuleEngineParameter,
        RuleExecutionLog,
        TestCase,
        TestCaseValue,
        RuleFunction,
        ContextRuleFunction,
        RunTestsReport,
        RuleError,
        RuleEngineTagRelation,
        module='rule_engine', type_='model')
    Pool.register(
        # From rule_engine
        RunTests,
        module='rule_engine', type_='wizard')
