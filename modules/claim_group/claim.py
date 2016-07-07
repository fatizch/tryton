# -*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__all__ = [
    'Claim',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    legal_entity = fields.Many2One('party.party', 'Legal Entity', select=True,
        ondelete='RESTRICT')
