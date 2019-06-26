# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import config
from . import party
from . import protocol


def register():
    Pool.register(
        batch.AlmerysProtocolBatch,
        config.AlmerysConfig,
        config.ConfigurationNumberSequenceV3,
        config.ConfigurationProtocolVersion,
        config.ConfigurationCustomerNumber,
        config.ConfigurationCustomerLabel,
        config.ConfigurationAutonomous,
        protocol.Protocol,
        party.Party,
        party.Address,
        module='third_party_protocol_almerys', type_='model')
