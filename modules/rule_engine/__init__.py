from trytond.pool import Pool
from .rule_engine import *


def register():
    Pool.register(
        RuleTools,
        Context,
        Rule,
        TestCase,
        TestCaseValue,
        TreeElement,
        ContextTreeElement,
        TestRuleStart,
        TestRuleTest,
        RunTestsReport,
        CreateTestCaseStart,
        CreateTestCaseAskDescription,
        TableDefinition,
        RuleError,
        module='rule_engine', type_='model')
    Pool.register(
        TestRule,
        CreateTestValues,
        RunTests,
        CreateTestCase,
        module='rule_engine', type_='wizard')
