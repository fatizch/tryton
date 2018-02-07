# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import export

__all__ = [
    'User',
    'Employee',
    ]


class User:
    __metaclass__ = PoolMeta
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
