from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import model, fields, coop_string, coop_date


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'LoanAveragePremiumRule',
    'FeeRule',
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


class LoanAveragePremiumRule(model.CoopSQL, model.CoopView):
    'Loan Average Premium Rule'

    __name__ = 'loan.average_premium_rule'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    use_default_rule = fields.Boolean('Use default Rule')
    default_fee_action = fields.Selection(FEE_ACTIONS, 'Default Fee Action',
        states={'invisible': ~Eval('use_default_rule')},
        depends=['use_default_rule'])
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
        result = {
            'contract_rule': None,
            'option_rule': None,
            'default_fee_action': 'prorata',
            }
        if self.fee_rules:
            result['fee_rules'] = {'remove': [x.id for x in self.fee_rules]}
        return result

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    def calculate_average_premium_for_contract(self, loan, contract):
        if not self.use_default_rule:
            # TODO : Plug in rules
            return 0
        premium_aggregates = contract.calculate_premium_aggregates()
        loan_amount = 0
        for k, v in premium_aggregates('contract').iteritems():
            if loan.id not in v:
                continue
            if k.__name__ == 'contract.option':
                option = k
            elif k.__name__ == 'contract.option.extra_premium':
                option = k.option
            for share in option.loan_shares:
                if share.loan == loan:
                    if share.share == 0:
                        break
                    loan_amount += v[loan.id] / share.share
                    break
        biggest = max([x.amount for x in contract.used_loans]) == loan.amount
        longest = max([coop_date.number_of_days_between(
                    x.funds_release_date,
                    x.end_date)
                for x in contract.used_loans]
            ) == coop_date.number_of_days_between(loan.funds_release_date,
                        loan.end_date)
        prorata_ratio = loan.amount / sum(
            [x.amount for x in contract.used_loans])
        fee_amount = 0
        ratios = {
            'longest': longest,
            'biggest': biggest,
            'prorata': prorata_ratio,
            }
        rule_fees = dict([(x.fee, x.action) for x in self.fee_rules])
        for k, v in premium_aggregates('offered').iteritems():
            if k.__name__ != 'account.fee.description':
                continue
            action = rule_fees.get(k, self.default_fee_action)
            if action == 'do_not_use':
                continue
            fee_amount += sum(v.values()) * ratios[action]
        den = loan.amount * coop_date.number_of_years_between(
            loan.funds_release_date, loan.end_date)
        return (loan_amount + fee_amount) * 100 / den if den else None

    def calculate_average_premium_for_option(self, contract, share):
        if not self.use_default_rule:
            # TODO : Plug in rules
            return 0
        loan = share.loan
        premium_aggregates = contract.calculate_premium_aggregates()
        share_amount = 0
        for entity in [share.option] + list(share.option.extra_premiums):
            share_amount += premium_aggregates('contract', value=entity,
                loan_id=share.loan.id)
        biggest = max([x.amount for x in contract.used_loans]) == loan.amount
        longest = max([coop_date.number_of_days_between(
                    x.funds_release_date,
                    x.end_date)
                for x in contract.used_loans]
            ) == coop_date.number_of_days_between(loan.funds_release_date,
                        loan.end_date)
        prorata_ratio = loan.amount / sum(
            [x.amount for x in contract.used_loans])
        fee_amount = 0
        ratios = {
            'longest': longest,
            'biggest': biggest,
            'prorata': prorata_ratio,
            }
        rule_fees = dict([(x.fee, x.action) for x in self.fee_rules])
        for k, v in premium_aggregates('offered').iteritems():
            if k.__name__ != 'account.fee.description':
                continue
            action = rule_fees.get(k, self.default_fee_action)
            if action == 'do_not_use':
                continue
            fee_amount += sum(v.values()) * ratios[action]
        denominator = (premium_aggregates('offered',
                model_name='offered.product') + premium_aggregates(
                'offered', model_name='offered.option.description'))
        if denominator == 0:
            fee_ratio = 0
        else:
            fee_ratio = share_amount / (premium_aggregates('offered',
                    model_name='offered.product') + premium_aggregates(
                    'offered', model_name='offered.option.description'))
        return (share_amount + fee_amount * fee_ratio) * 100 / (loan.amount *
            coop_date.number_of_years_between(loan.funds_release_date,
                loan.end_date) * share.share)


class FeeRule(model.CoopSQL, model.CoopView):
    'Fee Rule'

    __name__ = 'loan.average_premium_rule.fee_rule'

    fee = fields.Many2One('account.fee.description', 'Fee', required=True,
        ondelete='CASCADE')
    rule = fields.Many2One('loan.average_premium_rule', 'Rule', required=True,
        ondelete='CASCADE')
    action = fields.Selection(FEE_ACTIONS, 'Behaviour')
