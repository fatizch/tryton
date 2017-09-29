# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (CompanyValueMixin,
    CompanyMultiValueMixin)

from trytond.modules.coog_core import fields, model


__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    'ConfigurationDefaultQuoteNumberSequence',
    ]


class Configuration(CompanyMultiValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'offered.configuration'

    default_quote_number_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', 'Default Quote Number Sequence',
            domain=[
                ('code', '=', 'quote'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    @classmethod
    def default_default_quote_number_sequence(cls):
        return cls.multivalue_model(
            'default_quote_number_sequence'
            ).default_default_quote_number_sequence()


class ConfigurationDefaultQuoteNumberSequence(model.CoogSQL,
        CompanyValueMixin):
    'Configuration Default Quote Number Sequence'
    __name__ = 'offered.configuration.default_quote_number_sequence'

    configuration = fields.Many2One('offered.configuration', 'Configuration',
        ondelete='CASCADE', select=True)
    default_quote_number_sequence = fields.Many2One('ir.sequence',
        'Default Quote Number Sequence',
        domain=[
            ('code', '=', 'quote'),
            ('company', '=', Eval('context', {}).get('company', -1)),
            ])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ConfigurationDefaultQuoteNumberSequence, cls).__register__(
            module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('quote_number_sequence')
        value_names.append('default_quote_number_sequence')
        fields.append('company')
        migrate_property(
            'offered.product', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_default_quote_number_sequence(cls):
        company_id = Transaction().context.get('company', None)
        sequences = Pool().get('ir.sequence').search(
            [
                ('code', '=', 'quote'),
                ('company', '=', company_id),
            ])
        if len(sequences) == 1:
            return sequences[0].id
