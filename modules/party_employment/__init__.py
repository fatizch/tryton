# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from . import rule_engine
from . import api
from . import offered


def register():
    Pool.register(
        party.Employment,
        party.Party,
        party.EmploymentKind,
        party.EmploymentVersion,
        party.EmploymentWorkTimeType,
        rule_engine.RuleEngineRuntime,
        offered.ItemDescription,
        party.PartyWorkSection,
        module='party_employment', type_='model')

    Pool.register(
        api.APIParty,
        api.APIProduct,
        module='party_employment', type_='model', depends=['api'])
