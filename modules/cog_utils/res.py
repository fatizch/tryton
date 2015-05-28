from trytond.pool import PoolMeta
from trytond.config import config
from trytond.transaction import Transaction

from export import ExportImportMixin


__metaclass__ = PoolMeta

__all__ = [
    'Group',
    'User',
    'ResUserWarning',
    ]


class Group(ExportImportMixin):
    __name__ = 'res.group'
    func_key = 'name'

    @classmethod
    def _export_skips(cls):
        result = super(Group, cls)._export_skips()
        result.add('users')
        return result

    @classmethod
    def _export_light(cls):
        return set(['menu_access'])


class User(ExportImportMixin):
    __name__ = 'res.user'
    _func_key = 'login'

    @classmethod
    def _export_skips(cls):
        result = super(User, cls)._export_skips()
        result.add('salt')
        return result

    def get_status_bar(self, name):
        status = super(User, self).get_status_bar(name)
        env = config.get('database', 'env_name', default='')
        if env:
            env = env.replace('%{DB}', Transaction().cursor.dbname)
            status += ' - %s' % env
        return status


class ResUserWarning(ExportImportMixin):
    __name__ = 'res.user.warning'
