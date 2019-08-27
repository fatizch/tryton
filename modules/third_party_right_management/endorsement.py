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

    @classmethod
    def _export_skips(cls):
        return super()._export_skips() | {'third_party_protocols'}


class ThirdPartyProtocolEndorsementPart(model.CoogSQL):
    "Third Party Protocol - Endorsement Part"
    __name__ = 'third_party_manager_protocol-endorsement_part'

    endorsement_part = fields.Many2One('endorsement.part', "Endorsement Part",
        required=True, ondelete='CASCADE')
    protocol = fields.Many2One('third_party_manager.protocol', "Protocol",
        required=True, ondelete='CASCADE')

    @classmethod
    def _export_light(cls):
        return super()._export_light() | {'endorsement_part', 'protocol'}


class EndorsementContract(metaclass=PoolMeta):
    __name__ = 'endorsement.contract'

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        new_periods = []
        for option in instances['contract.option']:
            if option.third_party_periods:
                new_periods += option.third_party_periods
        instances['contract.option.third_party_period'] = new_periods
