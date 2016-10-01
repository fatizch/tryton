# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Insurer',
    ]


class Insurer:
    __name__ = 'insurer'

    waiting_account = fields.Many2One('account.account', 'Waiting Account',
        ondelete='RESTRICT')

    @classmethod
    def _export_light(cls):
        return (super(Insurer, cls)._export_light() | set(['waiting_account']))
