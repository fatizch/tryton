from trytond.pool import Pool
from .rule_engine import *


def register():
    Pool.register(
        RuleTools,
        Context,
        Rule,
        RuleExecutionLog,
        TestCase,
        TestCaseValue,
        TreeElement,
        ContextTreeElement,
        RunTestsReport,
        TableDefinition,
        RuleError,
        module='rule_engine', type_='model')
    Pool.register(
        RunTests,
        module='rule_engine', type_='wizard')
