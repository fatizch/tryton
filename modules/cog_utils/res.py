from trytond.pool import PoolMeta

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


class ResUserWarning(ExportImportMixin):
    __name__ = 'res.user.warning'
