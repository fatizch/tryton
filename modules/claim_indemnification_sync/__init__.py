# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import claim
import rule_engine
import wizard


def register():
    Pool.register(
        claim.Service,
        claim.Indemnification,
        rule_engine.RuleEngineRuntime,
        module='claim_indemnification_sync', type_='model')

    Pool.register(
        wizard.CreateIndemnification,
        module='claim_indemnification_sync', type_='wizard')
