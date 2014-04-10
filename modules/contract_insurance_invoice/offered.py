from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Product',
    'OptionDescription',
    'FeeDesc',
    'TaxDesc',
    ]


class Product:
    __name__ = 'offered.product'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', required=True, depends=['company'],
        domain=[('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        ondelete='RESTRICT')


class OptionDescription:
    __name__ = 'offered.option.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        states={
            'required': ~Eval('is_package'),
            'invisible': ~~Eval('is_package'),
            }, ondelete='RESTRICT')


class FeeDesc:
    __name__ = 'account.fee.description'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('context', {}).get('company'))],
        required=True, ondelete='RESTRICT')


class TaxDesc:
    __name__ = 'account.tax.description'

    tax = fields.Many2One('account.tax', 'Tax')
