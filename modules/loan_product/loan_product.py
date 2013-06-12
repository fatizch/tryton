#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils, fields

__all__ = [
    'LoanProduct',
    'LoanCoverage',
    ]


class LoanProduct():
    'Loan Product'

    __name__ = 'offered.product'
    __metaclass__ = PoolMeta

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan_product')

    def get_is_loan_product(self, name):
        for coverage in self.coverages:
            if coverage.is_loan:
                return True
        return False


class LoanCoverage():
    'Loan Coverage'

    __name__ = 'offered.coverage'
    __metaclass__ = PoolMeta

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan_coverage')

    @classmethod
    def __setup__(cls):
        super(LoanCoverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        utils.append_inexisting(cls.family.selection,
            ('loan', 'Loan'))

    def get_is_loan_coverage(self, name):
        return self.family == 'loan'

    def get_is_coverage_amount_needed(self, name=None):
        res = super(LoanCoverage, self).get_is_coverage_amount_needed(name)
        return res and not self.get_is_loan_coverage()
