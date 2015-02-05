import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import model, fields, coop_string, coop_date


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'LoanAveragePremiumRule',
    'FeeRule',
    'OptionDescriptionPremiumRule',
    'OptionDescription',
    'ProductPremiumDate',
    ]
FEE_ACTIONS = [
    ('do_not_use', 'Do not use fee'),
    ('longest', 'Apply on longest loan'),
    ('biggest', 'Apply on biggest loan'),
    ('prorata', 'Apply a prorata on loan amount'),
    ]


class Product:
    __name__ = 'offered.product'

    average_loan_premium_rule = fields.Many2One('loan.average_premium_rule',
        'Average Loan Premium Rule', states={
            'required': Bool(Eval('is_loan', False))},
        depends=['is_loan'], ondelete='RESTRICT')

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


class LoanAveragePremiumRule(model.CoopSQL, model.CoopView):
    'Loan Average Premium Rule'

    __name__ = 'loan.average_premium_rule'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    use_default_rule = fields.Boolean('Use default Rule')
    default_fee_action = fields.Selection(FEE_ACTIONS, 'Default Fee Action',
        states={'invisible': ~Eval('use_default_rule')},
        depends=['use_default_rule'])
    default_fee_action_string = default_fee_action.translated(
        'default_fee_action')
    contract_rule = fields.Many2One('rule_engine', 'Contract rule',
        ondelete='RESTRICT', states={
            'required': ~Eval('use_default_rule'),
            'invisible': Bool(Eval('use_default_rule', False))},
        depends=['use_default_rule'])
    option_rule = fields.Many2One('rule_engine', 'Option rule',
        ondelete='RESTRICT', states={
            'required': ~Eval('use_default_rule'),
            'invisible': Bool(Eval('use_default_rule', False))},
        depends=['use_default_rule'])
    fee_rules = fields.One2Many('loan.average_premium_rule.fee_rule', 'rule',
        'Fee Rules', states={'invisible': ~Eval('use_default_rule')},
        depends=['use_default_rule'])

    @classmethod
    def default_default_fee_action(cls):
        return 'prorata'

    @classmethod
    def default_use_default_rule(cls):
        return True

    @fields.depends('use_default_rule', 'fee_rules')
    def on_change_use_default_rule(self):
        self.contract_rule = None
        self.option_rule = None
        self.default_fee_action = 'prorata'
        if self.fee_rules:
            self.fee_rules = []

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.slugify(self.name)

    def calculate_average_premium_for_contract(self, loan, contract):
        if not self.use_default_rule:
            # TODO : Plug in rules
            return 0, 0
        pool = Pool()
        Fee = pool.get('account.fee')
        Option = pool.get('contract.option')
        ExtraPremium = pool.get('contract.option.extra_premium')
        loan_amount, insured_amount = 0, 0
        for k, v in contract.extract_premium('contract').iteritems():
            if loan.id not in v:
                continue
            if k[0] == 'contract.option':
                option = Option(k[1])
            elif k[0] == 'contract.option.extra_premium':
                option = ExtraPremium(k[1]).option
            for share in option.loan_shares:
                if share.loan == loan and share.share:
                    loan_amount += v[loan.id]
                    insured_amount = loan.amount * share.share
                    break

        loan_insured, max_insured = {}, 0
        for cur_loan in contract.used_loans:
            loan_insured[cur_loan.id] = cur_loan.amount * max([
                    x.share for x in cur_loan.current_loan_shares])
            max_insured = max(max_insured, loan_insured[cur_loan.id])
        biggest = max_insured == loan_insured[loan.id]
        longest = max([coop_date.number_of_days_between(
                    x.funds_release_date,
                    x.end_date)
                for x in contract.used_loans]
            ) == coop_date.number_of_days_between(loan.funds_release_date,
                        loan.end_date)
        prorata_ratio = loan_insured[loan.id] / sum(loan_insured.values())
        fee_amount = 0
        ratios = {
            'longest': longest,
            'biggest': biggest,
            'prorata': prorata_ratio,
            }
        rule_fees = dict([(x.fee, x.action) for x in self.fee_rules])
        for k, v in contract.extract_premium('offered').iteritems():
            if k[0] != 'account.fee':
                continue
            action = rule_fees.get(Fee(k[1]), self.default_fee_action)
            if action == 'do_not_use':
                continue
            fee_amount += sum(v.values()) * ratios[action]
        den = insured_amount * coop_date.number_of_years_between(
            loan.funds_release_date, loan.end_date)
        base_amount = loan_amount + fee_amount
        loan_average = base_amount * 100 / den if den else None
        return base_amount, loan_average

    def calculate_average_premium_for_option(self, contract, share):
        if not self.use_default_rule:
            # TODO : Plug in rules
            return 0, 0
        Fee = Pool().get('account.fee')
        loan = share.loan
        share_amount = 0
        for entity in [share.option] + list(share.option.extra_premiums):
            share_amount += contract.extract_premium('contract', value=entity,
                loan=share.loan)
        loan_insured, max_insured = {}, 0
        for cur_share in share.option.loan_shares:
            loan_insured[cur_share.loan.id] = cur_share.loan.amount * \
                cur_share.share
            max_insured = max(max_insured, loan_insured[cur_share.loan.id])
        biggest = max_insured == loan_insured[loan.id]
        longest = max([coop_date.number_of_days_between(
                    x.funds_release_date,
                    x.end_date)
                for x in contract.used_loans]
            ) == coop_date.number_of_days_between(loan.funds_release_date,
                        loan.end_date)
        prorata_ratio = loan_insured[loan.id] / sum(loan_insured.values())
        fee_amount = 0
        ratios = {
            'longest': longest,
            'biggest': biggest,
            'prorata': prorata_ratio,
            }
        rule_fees = dict([(x.fee, x.action) for x in self.fee_rules])
        for k, v in contract.extract_premium('offered').iteritems():
            if k[0] != 'account.fee':
                continue
            action = rule_fees.get(Fee(k[1]), self.default_fee_action)
            if action == 'do_not_use':
                continue
            fee_amount += sum(v.values()) * ratios[action]
        base_value = share_amount + fee_amount
        loan_average = base_value * 100 / (loan.amount *
            coop_date.number_of_years_between(loan.funds_release_date,
                loan.end_date) * share.share)
        return base_value, loan_average


class FeeRule(model.CoopSQL, model.CoopView):
    'Fee Rule'

    __name__ = 'loan.average_premium_rule.fee_rule'

    fee = fields.Many2One('account.fee', 'Fee', required=True,
        ondelete='CASCADE')
    rule = fields.Many2One('loan.average_premium_rule', 'Rule', required=True,
        ondelete='RESTRICT')
    action = fields.Selection(FEE_ACTIONS, 'Behaviour')
    action_string = action.translated('action')


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
        if not contract.is_loan:
            return res
        if self.type_ == 'every_loan_payment':
            return [payment.start_date
                for loan in contract.used_loans
                for payment in loan.payments]
