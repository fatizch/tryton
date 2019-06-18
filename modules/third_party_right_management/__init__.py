# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import offer
from . import event
from . import protocol
from . import endorsement
from . import rule_engine


def register():
    Pool.register(
        offer.ContractOption,
        offer.ThirdPartyPeriod,
        offer.Coverage,
        offer.ThirdPartyProtocolCoverage,
        protocol.RecomputePeriodAskDate,
        event.Event,
        protocol.Protocol,
        protocol.ProtocolEventType,
        rule_engine.RuleEngine,
        rule_engine.RuleTools,
        module='third_party_right_management', type_='model')
    Pool.register(
        protocol.ProtocolEndorsement,
        endorsement.EndorsementPart,
        endorsement.ThirdPartyProtocolEndorsementPart,
        module='third_party_right_management', type_='model',
        depends=['endorsement'])
    Pool.register(
        protocol.RecomputePeriod,
        module='third_party_right_management', type_='wizard')
