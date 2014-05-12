#-*- coding:utf-8 -*-
import copy
import datetime

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, fields
from trytond.modules.offered_insurance import offered


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescription',
    'PremiumRule',
    ]


class Product:
    __name__ = 'offered.product'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan_product')
    calculate_each_payment = fields.Boolean('Calculate each payment', states={
            'invisible': ~Eval('is_loan')}, depends=['is_loan'])

    @classmethod
    def default_calculate_each_payment(cls):
        return True

    def get_is_loan_product(self, name):
        for coverage in self.coverages:
            if coverage.is_loan:
                return True
        return False

    def get_loan_dates(self, dates, loan):
        if not self.calculate_each_payment:
            return
        for payment in loan.payments:
            dates.add(payment.start_date)

    def get_option_dates(self, dates, option):
        super(Product, self).get_option_dates(dates, option)
        for elem in option.loan_shares:
            dates.add(elem.start_date)

    def get_dates(self, contract):
        dates = super(Product, self).get_dates(contract)
        for loan in contract.loans:
            self.get_loan_dates(dates, loan)
        return dates


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

    def calculate_sub_elem_price(self, args, errs):
        if not self.is_loan:
            return super(OptionDescription, self).calculate_sub_elem_price(
                args, errs)
        lines = []
        for covered, option in self.give_me_covered_elements_at_date(
                args)[0]:
            tmp_args = args.copy()
            option.init_dict_for_rule_engine(tmp_args)
            for share in option.loan_shares:
                if not (share.start_date <= args['date'] <=
                        (share.end_date or datetime.date.max)):
                    continue
                share.init_dict_for_rule_engine(tmp_args)
                try:
                    sub_elem_lines, sub_elem_errs = self.get_result(
                        'sub_elem_price', tmp_args, kind='premium')
                except offered.NonExistingRuleKindException:
                    sub_elem_lines = []
                    sub_elem_errs = []
                errs += sub_elem_errs
                lines += sub_elem_lines
        return lines


class PremiumRule:
    __name__ = 'billing.premium.rule'

    def get_lowest_level_instance(self, args):
        if 'share' not in args:
            return super(PremiumRule, self).get_lowest_level_instance(args)
        return args['share']
