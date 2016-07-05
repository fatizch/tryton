# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .rule_engine import *
from .process import *


def register():
    Pool.register(
        RuleEngine,
        ProcessAction,
        module='process_rule', type_='model')
