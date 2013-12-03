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

    @classmethod
    def _export_skips(cls):
        result = super(Group, cls)._export_skips()
        result.add('users')
        return result

    @classmethod
    def _export_keys(cls):
        return set(['name'])

    @classmethod
    def _export_light(cls):
        return set(['menu_access'])


class User(ExportImportMixin):
    'User'

    __name__ = 'res.user'

    @classmethod
    def _export_keys(cls):
        return set(['login'])

    @classmethod
    def _export_skips(cls):
        result = super(User, cls)._export_skips()
        result.add('salt')
        return result

    def _export_override_password(self, exported, result, my_key):
        return ''

    @classmethod
    def _import_override_password(cls, instance_key, good_instance,
            field_value, values, created, relink):
        if good_instance.id:
            # Do not try to override the password
            return
        # For new users, set the login as password in the new db
        good_instance.password = values['login']
        return


class ResUserWarning(ExportImportMixin):
    'User Warning'

    __name__ = 'res.user.warning'

    @classmethod
    def _export_keys(cls):
        return set(['name', 'user.login'])
