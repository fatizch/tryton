# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from . import rule_engine
from . import api
from . import offered


def register():
    Pool.register(
        party.Party,
        party.EmploymentVersion,
        party.AdminSituationSubStatus,
        party.PublicEmploymentIndex,
        rule_engine.RuleEngineRuntime,
        party.EmploymentKind,
        party.Employment,
        offered.ItemDescription,
        module='party_public_employment', type_='model')

    Pool.register(
        api.APIParty,
        module='party_public_employment', type_='model', depends=['api'])
