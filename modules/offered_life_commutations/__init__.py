# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import commutation
import rule_engine


def register():
    Pool.register(
        commutation.CommutationManager,
        commutation.CommutationManagerLine,
        rule_engine.RuleRuntime,
        module='offered_life_commutations', type_='model')
