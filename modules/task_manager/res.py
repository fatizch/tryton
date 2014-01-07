from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'User',
]


class User:
    __name__ = 'res.user'

    team = fields.Many2One('res.team', 'Team')

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('team')
        return result
