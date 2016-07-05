# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    ]


class Product:
    __name__ = 'offered.product'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan_product')

    def get_is_loan_product(self, name):
        for coverage in self.coverages:
            if coverage.is_loan:
                return True
        return False


class OptionDescription:
    __name__ = 'offered.option.description'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan_coverage')

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('loan', 'Loan'))

    def get_is_loan_coverage(self, name):
        return self.family == 'loan'
