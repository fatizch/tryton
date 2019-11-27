# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import config
from . import party
from . import protocol
from . import offered
from . import almerys


def register():
    Pool.register(
        batch.AlmerysProtocolBatch,
        batch.AlmerysFeedbackBatch,
        config.AlmerysConfig,
        config.ConfigurationNumberSequenceV3,
        config.ConfigurationProtocolVersion,
        config.ConfigurationCustomerNumber,
        config.ConfigurationCustomerLabel,
        config.ConfigurationAutonomous,
        protocol.Protocol,
        almerys.ReturnAlmerys,
        party.Party,
        party.Address,
        offered.ThirdPartyPeriod,
        module='third_party_protocol_almerys', type_='model')
    Pool.register(
        almerys.RecomputePeriod,
        module='third_party_protocol_almerys', type_='wizard')
