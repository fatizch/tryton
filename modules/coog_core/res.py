# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.config import config
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields
from trytond.modules import get_module_info
from trytond.cache import Cache

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

    version_module = config.get('version', 'module', default='coog_core')
    version_cache = Cache('version_cache')
    color_bg = fields.Function(fields.Char('Background Color'), 'get_color_bg')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields.append('color_bg')

    @classmethod
    def _export_skips(cls):
        result = super(User, cls)._export_skips()
        result.add('salt')
        return result

    def get_status_bar(self, name):
        status = super(User, self).get_status_bar(name)
        env = config.get('database', 'env_name', default='')
        if env:
            env = env.replace('%{DB}', Transaction().database.name)
            status += ' - %s' % env
        version = self.version_cache.get(self.version_module, -1)
        if version == -1:
            version = get_module_info(self.version_module).get('version')
            self.version_cache.set(self.version_module, version)
        status += (' - Version %s' % version)
        return status

    def get_color_bg(self, name):
        db = Transaction().database.name
        color = config.get('database', db, default=None)
        if color:
            return '#%s' % color

    @classmethod
    def _export_light(cls):
        return super(User, cls)._export_light() | {'groups', 'rule_groups'}


class ResUserWarning(ExportImportMixin):
    __name__ = 'res.user.warning'
