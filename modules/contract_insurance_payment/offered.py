# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, coog_string

__all__ = [
    'Product',
    'BillingMode',
    ]


class Product(metaclass=PoolMeta):
    __name__ = 'offered.product'

    payment_journal = fields.Many2One('account.payment.journal',
        'Payment Journal', domain=[('process_method', '!=', 'manual')],
        ondelete='RESTRICT',
        help='Payment journal used when billing mode is set to direct debit.'
        'If no journal defined the global configuration will be used')

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'payment_journal'}

    def get_documentation_structure(self):
        doc = super(Product, self).get_documentation_structure()
        doc['parameters'].append(
            coog_string.doc_for_field(self, 'payment_journal'))
        return doc


class BillingMode(metaclass=PoolMeta):
    __name__ = 'offered.billing_mode'

    failure_billing_mode = fields.Many2One('offered.billing_mode',
        'Failure Billing Mode', ondelete='RESTRICT',
        domain=[('direct_debit', '=', False)],
        states={'invisible': ~Eval('direct_debit')},
        depends=['direct_debit'])
