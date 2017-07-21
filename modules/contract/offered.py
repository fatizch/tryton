# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta
from trytond import backend
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (CompanyMultiValueMixin,
    CompanyValueMixin)

from trytond.modules.coog_core import fields, model

__all__ = [
    'Product',
    'ProductQuoteNumberSequence'
    ]
__metaclass__ = PoolMeta


class Product(CompanyMultiValueMixin):
    __name__ = 'offered.product'
    __metaclass__ = PoolMeta

    quote_number_sequence = fields.MultiValue(fields.Many2One('ir.sequence',
            'Quote number sequence', domain=[
                ('code', '=', 'quote'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ],
            states={
                'required': Bool(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))

    @classmethod
    def _export_light(cls):
        return (super(Product, cls)._export_light() |
            set(['quote_number_sequence']))


class ProductQuoteNumberSequence(model.CoogSQL, CompanyValueMixin):
    'Product Quote Number Sequence'
    __name__ = 'offered.product.quote_number_sequence'

    product = fields.Many2One('offered.product', 'Product', ondelete='CASCADE',
        select=True)
    quote_number_sequence = fields.Many2One('ir.sequence',
        'Quote Number Sequence', domain=[('code', '=', 'quote'),
            ('company', '=', Eval('company', -1))],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(ProductQuoteNumberSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('quote_number_sequence')
        value_names.append('quote_number_sequence')
        fields.append('company')
        migrate_property(
            'offered.product', field_names, cls, value_names,
            parent='product', fields=fields)
