# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields

__all__ = [
    'Claim',
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

    def get_recipients(self):
        recipients = [self.legal_entity] if self.legal_entity else []
        recipients += super(Claim, self).get_recipients()
        return recipients
