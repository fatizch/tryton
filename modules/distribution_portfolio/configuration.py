# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond import backend
from trytond.tools.multivalue import migrate_property
from trytond.modules.coog_core import fields, model
from trytond.modules.company.model import (CompanyValueMixin,
    CompanyMultiValueMixin)

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    'ConfigurationDefaultPortfolio',
    ]


class Configuration(CompanyMultiValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.configuration'

    default_portfolio = fields.MultiValue(
        fields.Many2One('distribution.network', 'Default Portfolio',
            domain=[('is_portfolio', '=', True)],
            help='This is the default portfolio if the user is not assigned to'
            ' any distribution network belonging to a portfolio.'))


class ConfigurationDefaultPortfolio(model.CoogSQL, CompanyValueMixin):
    'Configuration Default Portfolio'
    __name__ = 'party.configuration.default_portfolio'

    configuration = fields.Many2One('party.configuration', 'Configuration',
        ondelete='CASCADE', select=True)
    default_portfolio = fields.Many2One('distribution.network',
        'Default Portfolio', domain=[('is_portfolio', '=', True)],
        help='This is the default portfolio if the user is not assigned to'
        ' any distribution network belonging to a portfolio.')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationDefaultPortfolio, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('default_portfolio')
        value_names.append('default_portfolio')
        migrate_property(
            'party.configuration', field_names, cls, value_names,
            parent='configuration', fields=fields)
