# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Id

from trytond.modules.coog_core import fields

__all__ = [
    'Fee',
    'Configuration',
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    @classmethod
    def __setup__(cls):
        super(Configuration, cls).__setup__()
        cls._error_messages.update({
                'rounding_document_method_error': 'Following products or '
                'coverages : %s have tax included option which is not allowed '
                'with document rounding method.'
                })

    def check_taxes_included_option(self, company):
        pool = Pool()
        Product = pool.get('offered.product')
        Option = pool.get('offered.option.description')
        products = Product.search([('company', '=', company.id),
                ('taxes_included_in_premium', '=', True)])
        if products:
            self.raise_user_error('rounding_document_method_error',
                ','.join([product.name for product in products]))
        options = Option.search([('company', '=', company.id),
                ('taxes_included_in_premium', '=', True)])
        if options:
            self.raise_user_error('rounding_document_method_error',
                ','.join([option.name for option in options]))

    @classmethod
    def validate(cls, configurations):
        pool = Pool()
        Company = pool.get('company.company')
        ConfigurationTaxRounding = pool.get(
            'account.configuration.tax_rounding')
        super(Configuration, cls).validate(configurations)
        for company in Company.search([]):
            found_match = False
            for line in ConfigurationTaxRounding.search(
                    [('company', '=', company)]):
                found_match = True
                if line.tax_rounding == 'document':
                    configurations[0].check_taxes_included_option(company)
            if not found_match:
                # By default configuration is per document
                configurations[0].check_taxes_included_option(company)


class Fee:
    __metaclass__ = PoolMeta
    __name__ = 'account.fee'

    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'service'),
            ('default_uom', '=', Id('product', 'uom_unit')),
            ('template.type', '=', 'service'),
            ('template.default_uom', '=', Id('product', 'uom_unit')),
            ], ondelete='RESTRICT')

    def get_account_for_billing(self, line):
        return self.product.template.account_revenue_used
