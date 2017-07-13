# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import rule_engine
import process


def register():
    Pool.register(
        rule_engine.RuleEngine,
        process.ProcessAction,
        module='process_rule', type_='model')
