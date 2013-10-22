from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__all__ = [
    'User',
    ]


class User():
    'User'

    __name__ = 'res.user'
    __metaclass__ = PoolMeta

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network')

    @classmethod
    def _export_skips(cls):
        result = super(User, cls)._export_skips()
        result.add('employee')
        return result
