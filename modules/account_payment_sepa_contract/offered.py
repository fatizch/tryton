# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields, coog_string

__all__ = [
    'Product',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    sepa_mandate_sequence = fields.Many2One('ir.sequence',
        "SEPA Mandate Sequence", domain=[
            ('code', '=', 'account.payment.sepa.mandate')],
        ondelete='RESTRICT', help='Sequence used to generate the sepa '
        'mandate identification number')

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'sepa_mandate_sequence'))
        return doc
