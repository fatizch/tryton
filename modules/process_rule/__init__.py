from trytond.pool import Pool
from .rule_engine import *
from .process import *


def register():
    Pool.register(
        RuleEngine,
        ProcessAction,
        module='process_rule', type_='model')
