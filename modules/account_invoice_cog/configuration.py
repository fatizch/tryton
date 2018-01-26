# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.cache import Cache

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    default_customer_payment_term = fields.Many2One(
        'account.invoice.payment_term', string='Default Customer Payment Term',
        ondelete='SET NULL')

    _get_tax_rounding_cache = Cache('_get_tax_rounding_cache')

    @classmethod
    def write(cls, *args):
        cls._get_tax_rounding_cache.clear()
        super(Configuration, cls).write(*args)

    @classmethod
    def delete(cls, *args):
        cls._get_tax_rounding_cache.clear()
        super(Configuration, cls).delete(*args)

    @property
    def _tax_rounding(self):
        context = Transaction().context
        pattern = {'company': context.get('company')}
        method = self.__class__._get_tax_rounding_cache.get(
            (self.id, 'company', context.get('company')), None)
        if method is not None:
            return method

        method = super(Configuration, self).on_change_with_tax_rounding(None,
            pattern)
        self.__class__._get_tax_rounding_cache.set(
            (self.id, 'company', context.get('company')), method)
        return method
