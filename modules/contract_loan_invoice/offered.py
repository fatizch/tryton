# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields, coop_date


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'OptionDescriptionPremiumRule',
    'OptionDescription',
    'ProductPremiumDate',
    ]


class Product:
    __name__ = 'offered.product'

    def get_option_dates(self, dates, option):
        super(Product, self).get_option_dates(dates, option)
        for elem in option.loan_shares:
            if elem.start_date:
                dates.add(elem.start_date)
            if elem.end_date:
                dates.add(coop_date.add_day(elem.end_date, 1))

    def get_dates(self, contract):
        dates = super(Product, self).get_dates(contract)
        for loan in contract.used_loans:
            dates.add(loan.funds_release_date)
            dates.add(loan.first_payment_date)
            dates.add(loan.end_date)
        return dates


class OptionDescriptionPremiumRule:
    __name__ = 'offered.option.description.premium_rule'

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionPremiumRule, cls).__setup__()
        cls.premium_base.selection.append(
            ('loan.share', 'Loan'))

    @fields.depends('coverage')
    def on_change_with_premium_base(self, name=None):
        if self.coverage and self.coverage.is_loan:
            return 'loan.share'
        return super(OptionDescriptionPremiumRule,
            self).on_change_with_premium_base(name)

    @classmethod
    def get_premium_result_class(cls):
        Parent = super(OptionDescriptionPremiumRule,
            cls).get_premium_result_class()

        class Child(Parent):
            def __init__(self, amount, data_dict):
                super(Child, self).__init__(amount, data_dict)
                self.loan = self.data_dict.get('loan', None)

        return Child

    def must_be_rated(self, rated_instance, date):
        LoanShare = Pool().get('loan.share')
        if isinstance(rated_instance, LoanShare):
            return super(OptionDescriptionPremiumRule, self).must_be_rated(
                rated_instance.option, date) and (
                (rated_instance.start_date or datetime.date.min) <=
                date <= (rated_instance.end_date or datetime.date.max))
        return super(OptionDescriptionPremiumRule, self).must_be_rated(
            rated_instance, date)

    @classmethod
    def get_not_rated_line(cls, rule_dict, date):
        # Loan shares that must not be rated should not create an empty line if
        # there is a new share for the same loan
        if rule_dict['_rated_instance'].__name__ == 'loan.share':
            share = rule_dict['_rated_instance']
            if share.start_date and share.start_date > date:
                return []
            shares = [x for x in share.option.loan_shares
                if x.loan == share.loan and x.start_date and x.start_date > (
                    share.start_date or datetime.date.min)]
            # option.loan_shares are sorted per loan / start
            if shares and shares[0].start_date == coop_date.add_day(
                    share.end_date, 1):
                return []
        return super(OptionDescriptionPremiumRule, cls).get_not_rated_line(
            rule_dict, date)


class OptionDescription:
    __name__ = 'offered.option.description'

    def get_rated_instances(self, base_instance):
        result = super(OptionDescription,
            self).get_rated_instances(base_instance)
        pool = Pool()
        Option = pool.get('contract.option')
        LoanShare = pool.get('loan.share')
        if isinstance(base_instance, Option):
            if base_instance.coverage == self:
                for loan_share in base_instance.loan_shares:
                    result += self.get_rated_instances(loan_share)
        elif isinstance(base_instance, LoanShare):
            result.append(base_instance)
        return result


class ProductPremiumDate:
    __name__ = 'offered.product.premium_date'

    @classmethod
    def __setup__(cls):
        super(ProductPremiumDate, cls).__setup__()
        cls.type_.selection.append(
            ('every_loan_payment', 'On Each Loan Payment'))

    def get_rule_for_contract(self, contract):
        res = super(ProductPremiumDate, self).get_rule_for_contract(contract)
        if res:
            return res
        if not contract.is_loan:
            return res
        if self.type_ == 'every_loan_payment':
            return [datetime.datetime.combine(
                    payment.start_date, datetime.time())
                for loan in contract.used_loans
                for payment in loan.payments]
