# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Claim',
    'ClaimService',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    legal_entity = fields.Many2One('party.party', 'Legal Entity', select=True,
        ondelete='RESTRICT')
    interlocutor = fields.Many2One('party.interlocutor', 'Interlocutor',
        ondelete='RESTRICT', domain=[
            ('party', '=', Eval('legal_entity'))
            ], depends=['legal_entity'])
    management_start_date = fields.Date('Management Start Date')
    management_end_date = fields.Date('Management End Date')

    def get_recipients(self):
        recipients = [self.legal_entity] if self.legal_entity else []
        recipients += super(Claim, self).get_recipients()
        return recipients


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def get_beneficiaries_data(self, at_date):
        if self.benefit.beneficiary_kind == 'subscriber_then_covered':
            covered = self.theoretical_covered_element
            if not covered:
                return [(self.contract.subscriber, 1)]
            elif (not covered.contract_exit_date or
                    covered.contract_exit_date > at_date):
                return [(self.contract.subscriber, 1)]
            return [(covered.party, 1)]
        return super(ClaimService, self).get_beneficiaries_data(at_date)
