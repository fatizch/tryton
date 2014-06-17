from trytond.pool import PoolMeta
from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'User',
    'Employee',
    ]


class User:
    __name__ = 'res.user'

    @classmethod
    def _export_skips(cls):
        result = super(User, cls)._export_skips()
        result.add('employee')
        return result

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('main_company')
        result.add('company')
        return result


class Employee(export.ExportImportMixin):
    __name__ = 'company.employee'

    @classmethod
    def _export_keys(cls):
        return set(['party.name', 'company.party.name'])
