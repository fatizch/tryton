# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.cog_utils import fields

__all__ = [
    'Configuration',
    'MoveLine',
    ]

__metaclass__ = PoolMeta


class Configuration:
    'Account Configuration'

    __name__ = 'account.configuration'

    cash_value_journal = fields.Property(
        fields.Many2One('account.journal', 'Cash Value Journal', domain=[
                ('type', '=', 'general')]))


class MoveLine:
    'Move Line'

    __name__ = 'account.move.line'

    @classmethod
    def _get_second_origin(cls):
        result = super(MoveLine, cls)._get_second_origin()
        result.append('contract.cash_value.collection')
        return result
