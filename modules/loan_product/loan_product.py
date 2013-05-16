#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils

__all__ = [
    'LoanProduct',
    'LoanCoverage',

]


class LoanProduct():
    'Loan Product'

    __name__ = 'ins_product.product'
    __metaclass__ = PoolMeta

    def get_is_loan_product(self):
        for coverage in self.coverages:
            if coverage.get_is_loan_coverage():
                return True
        return False


class LoanCoverage():
    'Loan Coverage'

    __name__ = 'ins_product.coverage'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(LoanCoverage, cls).__setup__()
        cls.family = copy.copy(cls.family)
        if not cls.family.selection:
            cls.family.selection = []
        utils.append_inexisting(cls.family.selection,
            ('loan', 'Loan'))
        if ('default', 'default') in cls.family.selection:
            cls.family.selection.remove(('default', 'default'))

    def get_is_loan_coverage(self):
        return self.family == 'loan'

    def get_is_coverage_amount_needed(self, name=None):
        res = super(LoanCoverage, self).get_is_coverage_amount_needed(name)
        return res and not self.get_is_loan_coverage()
