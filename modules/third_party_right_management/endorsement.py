# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.coog_core import model, fields


class EndorsementPart(metaclass=PoolMeta):
    __name__ = 'endorsement.part'

    third_party_protocols = fields.Many2Many(
        'third_party_manager_protocol-endorsement_part',
        'endorsement_part', 'protocol', "Third Party Protocols",
        domain=[
            ('watched_events.code', '=', 'apply_endorsement')
            ])


class ThirdPartyProtocolEndorsementPart(model.CoogSQL):
    "Third Party Protocol - Endorsement Part"
    __name__ = 'third_party_manager_protocol-endorsement_part'

    endorsement_part = fields.Many2One('endorsement.part', "Endorsement Part",
        required=True, ondelete='CASCADE')
    protocol = fields.Many2One('third_party_manager.protocol', "Protocol",
        required=True, ondelete='CASCADE')
