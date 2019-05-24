# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields, coog_string

__all__ = [
    'Product'
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    dunning_procedure = fields.Many2One('account.dunning.procedure',
        'Dunning Procedure', ondelete='RESTRICT', help='Dunning procedure '
        'used for contract pre-litigation')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'dunning_procedure'}

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'dunning_procedure'))
        return doc
