# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond import backend
from trytond.tools.multivalue import migrate_property
from trytond.modules.coog_core import fields, model
from trytond.modules.company.model import (CompanyValueMixin,
    CompanyMultiValueMixin)


__all__ = [
    'Configuration',
    'ConfigurationCashValueJournal',
    'MoveLine',
    ]

__metaclass__ = PoolMeta


class Configuration(CompanyMultiValueMixin):
    'Account Configuration'

    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    cash_value_journal = fields.MultiValue(
        fields.Many2One('account.journal', 'Cash Value Journal', domain=[
                ('type', '=', 'general')]))


class ConfigurationCashValueJournal(model.CoogSQL, CompanyValueMixin):
    'Account Configuration Cash Value Journal'
    __name__ = 'account.configuration.cash_value_journal'

    configuration = fields.Many2One('account.configuration', 'Configuration',
        ondelete='CASCADE', select=True)
    cash_value_journal = fields.Many2One('account.journal',
        'Cash Value Journal', domain=[('type', '=', 'general')])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationCashValueJournal, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('cash_value_journal')
        value_names.append('cash_value_journal')
        fields.append('type')
        migrate_property(
            'account.configuration', field_names, cls, value_names,
            parent='configuration', fields=fields)

class MoveLine:
    'Move Line'

    __name__ = 'account.move.line'

    @classmethod
    def _get_second_origin(cls):
        result = super(MoveLine, cls)._get_second_origin()
        result.append('contract.cash_value.collection')
        return result
