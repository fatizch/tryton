# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import offered
from . import event
from . import protocol
from . import endorsement
from . import rule_engine
from . import suspension
from . import contract


def register():
    Pool.register(
        offered.ContractOption,
        offered.ThirdPartyPeriod,
        offered.Coverage,
        offered.ThirdPartyProtocolCoverage,
        protocol.RecomputePeriodAskDate,
        event.Event,
        protocol.Protocol,
        protocol.ProtocolEventType,
        rule_engine.RuleEngine,
        rule_engine.RuleTools,
        contract.Contract,
        module='third_party_right_management', type_='model')
    Pool.register(
        protocol.ProtocolEndorsement,
        endorsement.EndorsementPart,
        endorsement.ThirdPartyProtocolEndorsementPart,
        endorsement.EndorsementContract,
        module='third_party_right_management', type_='model',
        depends=['endorsement'])
    Pool.register(
        suspension.ContractRightSuspension,
        module='third_party_right_management', type_='model',
        depends=['contract_insurance_suspension'],
        )
    Pool.register(
        protocol.RecomputePeriod,
        module='third_party_right_management', type_='wizard')
