from trytond.pool import Pool
from .rule_engine import *


def register():
    Pool.register(
        Context,
        Rule,
        TreeElement,
        ContextTreeElement,
        TestRuleStart,
        TestRuleTest,
        module='rule_engine', type_='model')
    Pool.register(
        TestRule,
        module='rule_engine', type_='wizard')
