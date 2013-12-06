from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__all__ = [
    'User',
]

__metaclass__ = PoolMeta


class User():
    'User'

    __name__ = 'res.user'

    team = fields.Many2One('task_manager.team', 'Team')

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('team')
        return result



