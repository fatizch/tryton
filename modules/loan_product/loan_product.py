#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils, fields
from trytond.modules.insurance_product import product


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

    def calculate_sub_elem_price(self, args, result_line, errs):
        if not self.is_loan:
            return super(LoanCoverage, self).calculate_sub_elem_price(args,
                result_line, errs)
        for covered, covered_data in self.give_me_covered_elements_at_date(
                args)[0]:
            tmp_args = args.copy()
            covered_data.init_dict_for_rule_engine(tmp_args)
            for share in covered_data.loan_shares:
                share.init_dict_for_rule_engine(tmp_args)
                try:
                    sub_elem_line, sub_elem_errs = self.get_result(
                        'sub_elem_price', tmp_args, kind='pricing')
                except product.NonExistingRuleKindException:
                    sub_elem_line = None
                    sub_elem_errs = []
                if sub_elem_line and sub_elem_line.amount:
                    sub_elem_line.on_object = share
                    result_line.add_detail_from_line(sub_elem_line)
                errs += sub_elem_errs
