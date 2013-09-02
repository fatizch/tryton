from trytond.pool import Pool
from .rule_engine import *
from .tag import *


def register():
    Pool.register(
        #from tag
        Tag,
        # from Rule Engine
        RuleTools,
        Context,
        Rule,
        RuleEngineParameter,
        RuleExecutionLog,
        TestCase,
        TestCaseValue,
        TreeElement,
        ContextTreeElement,
        RunTestsReport,
        RuleError,
        RuleEngineTagRelation,
        module='rule_engine', type_='model')
    Pool.register(
        RunTests,
        module='rule_engine', type_='wizard')
