from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'User',
    ]


class User:
    'User'

    __name__ = 'res.user'

    dist_network = fields.Many2One('distribution.network',
        'Distribution Network')

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('dist_network')
        return result
