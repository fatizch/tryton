# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party
from . import rule_engine


def register():
    Pool.register(
        party.Party,
        party.EmploymentVersion,
        party.AdminSituationSubStatus,
        party.PublicEmploymentIndex,
        rule_engine.RuleEngineRuntime,
        party.EmploymentKind,
        party.Employment,
        module='party_public_employment', type_='model')
