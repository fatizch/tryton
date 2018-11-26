# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import health
from . import party
from . import contract
from . import rule_engine
from . import test_case


def register():
    Pool.register(
        party.Party,
        party.PartyRelation,
        health.HealthCareSystem,
        health.InsuranceFund,
        party.HealthPartyComplement,
        contract.CoveredElement,
        contract.Contract,
        rule_engine.RuleEngineRuntime,
        test_case.TestCaseModel,
        module='contract_insurance_health_fr', type_='model')
