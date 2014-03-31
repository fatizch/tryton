#-*- coding:utf-8 -*-
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields
from trytond.modules.offered_insurance import offered
from trytond.modules.offered import PricingResultLine


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

    def calculate_sub_elem_price(self, args, result_line, errs):
        if not self.is_loan:
            return super(OptionDescription, self).calculate_sub_elem_price(
                args, result_line, errs)
        for covered, covered_data in self.give_me_covered_elements_at_date(
                args)[0]:
            tmp_args = args.copy()
            result = PricingResultLine()
            result.on_object = covered_data
            covered_data.init_dict_for_rule_engine(tmp_args)
            for share in covered_data.loan_shares:
                share.init_dict_for_rule_engine(tmp_args)
                try:
                    sub_elem_line, sub_elem_errs = self.get_result(
                        'sub_elem_price', tmp_args, kind='premium')
                except offered.NonExistingRuleKindException:
                    sub_elem_line = None
                    sub_elem_errs = []
                if sub_elem_line and sub_elem_line.amount:
                    sub_elem_line.on_object = share
                    result.add_detail_from_line(sub_elem_line)
                errs += sub_elem_errs
            result_line.add_detail_from_line(result)
