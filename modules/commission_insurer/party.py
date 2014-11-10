from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Insurer',
    ]


class Insurer:
    __name__ = 'insurer'

    waiting_account = fields.Many2One('account.account', 'Waiting Account')
