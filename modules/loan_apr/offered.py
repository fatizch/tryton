# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
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
    name = fields.Char('Name', required=True, translate=True)
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
        depends=['use_default_rule'], delete_missing=True)

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
                    insured_amount = max(insured_amount,
                        loan.amount * share.share)
                    break

        loan_insured, max_insured = {}, 0
        for cur_loan in contract.used_loans:
            loan_insured[cur_loan.id] = cur_loan.amount * max([
                    x.share for x in cur_loan.current_loan_shares])
            max_insured = max(max_insured, loan_insured[cur_loan.id])
        prorata_ratio = loan_insured[loan.id] / sum(loan_insured.values())
        fee_amount = 0

        # Weird algorithm. Fees can be affected to 'biggest' loan, 'longest'
        # loan, or proratized accross loans depending on insurance amount.
        #
        # In case of 'duplicates' (i.e. : two loans with the same duration),
        # the secondary rule is used (i.e. : discriminate on amount). In case
        # of another duplicate (tough luck...) the first loan in order on the
        # contract is used.
        biggest_loans = {k for k, v in loan_insured.items()
            if max_insured == v}
        longest_duration = max([coop_date.number_of_days_between(
                    x.funds_release_date,
                    x.end_date)
                for x in contract.used_loans])
        longest_loans = {x.id for x in contract.used_loans
            if coop_date.number_of_days_between(x.funds_release_date,
                x.end_date) == longest_duration}
        top_loans = longest_loans & biggest_loans
        biggest, longest = None, None
        if top_loans and loan.id in top_loans:
            if len(top_loans) == 1:
                is_top = True
            else:
                is_top = loan.id == [x.loan.id
                    for x in contract.ordered_loans
                    if x.loan.id in top_loans][0]
            biggest, longest = is_top, is_top
        elif top_loans:
            biggest, longest = False, False
        if biggest is None:
            if loan.id in biggest_loans:
                if len(biggest_loans) == 1:
                    biggest = True
                else:
                    biggest = loan.id == [x.loan.id
                        for x in contract.ordered_loans
                        if x.loan.id in biggest_loans][0]
            else:
                biggest = False
        if longest is None:
            if loan.id in longest_loans:
                if len(longest_loans) == 1:
                    longest = True
                else:
                    longest = loan.id == [x.loan.id
                        for x in contract.ordered_loans
                        if x.loan.id in longest_loans][0]
            else:
                longest = False
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
        prorata_ratio = loan_insured[loan.id] / sum(loan_insured.values())
        fee_amount = 0

        # Same algorithm than for contract-wide average premium rate
        biggest_loans = {k for k, v in loan_insured.items()
            if max_insured == v}
        longest_duration = max([coop_date.number_of_days_between(
                    x.funds_release_date,
                    x.end_date)
                for x in contract.used_loans])
        longest_loans = {x.id for x in contract.used_loans
            if coop_date.number_of_days_between(x.funds_release_date,
                x.end_date) == longest_duration}
        top_loans = longest_loans & biggest_loans
        biggest, longest = None, None
        if top_loans and loan.id in top_loans:
            if len(top_loans) == 1:
                is_top = True
            else:
                is_top = loan.id == [x.loan.id
                    for x in contract.ordered_loans
                    if x.loan.id in top_loans][0]
            biggest, longest = is_top, is_top
        elif top_loans:
            biggest, longest = False, False
        if biggest is None:
            if loan.id in biggest_loans:
                if len(biggest_loans) == 1:
                    biggest = True
                else:
                    biggest = loan.id == [x.loan.id
                        for x in contract.ordered_loans
                        if x.loan.id in biggest_loans][0]
            else:
                biggest = False
        if longest is None:
            if loan.id in longest_loans:
                if len(longest_loans) == 1:
                    longest = True
                else:
                    longest = loan.id == [x.loan.id
                        for x in contract.ordered_loans
                        if x.loan.id in longest_loans][0]
            else:
                longest = False
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
        ondelete='RESTRICT', select=True)
    action = fields.Selection(FEE_ACTIONS, 'Behaviour')
    action_string = action.translated('action')
