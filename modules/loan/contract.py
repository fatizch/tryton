# -*- coding: utf-8 -*-
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, fields, model, coop_string

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    'ExtraPremium',
    'LoanShare',
    ]


class Contract:
    __name__ = 'contract'

    is_loan = fields.Function(
        fields.Boolean('Is Loan'),
        'on_change_with_is_loan')
    loans = fields.Function(
        fields.Many2Many('loan', None, None, 'Loans',
            domain=[('parties', 'in', Eval('parties'))],
            states={
                'invisible': (~Eval('is_loan')) | (~Eval('subscriber', False)),
                'readonly': Eval('status') != 'quote',
                },
            depends=['is_loan', 'currency', 'status', 'subscriber', 'parties'],
            context={
                'currency': Eval('currency'),
                'party': Eval('subscriber')}),
        'on_change_with_loans', 'setter_void')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.covered_elements.context.update({
                'is_loan': Eval('is_loan')})
        cls.covered_elements.depends.append('is_loan')
        cls.options.context.update({
                'is_loan': Eval('is_loan'),
                'subscriber_loans': Eval('loans', [])})
        cls.options.depends.append('is_loan')
        cls.options.depends.append('loans')
        cls._buttons.update({
                'create_loan': {'invisible': Eval('status') != 'quote'},
                })

    @fields.depends('product')
    def on_change_product(self):
        result = super(Contract, self).on_change_product()
        result['is_loan'] = self.product.is_loan if self.product else False
        if not result['is_loan']:
            result['loans'] = []
        return result

    @fields.depends('product')
    def on_change_with_is_loan(self, name=None):
        return self.product.is_loan if self.product else False

    @fields.depends('subscriber')
    def on_change_with_loans(self, name=None):
        if not self.subscriber:
            return []
        return [x.loan.id for x in Pool().get('loan-party').search([
                ('party', '=', self.subscriber)])]

    @classmethod
    @model.CoopView.button_action('loan.launch_loan_creation_wizard')
    def create_loan(cls, loans):
        pass

    def set_contract_end_date_from_loans(self):
        if not self.loans:
            return
        end_date = max([x.end_date for x in self.loans])
        self.end_date = end_date


class ContractOption:
    __name__ = 'contract.option'

    loan_shares = fields.One2Many('loan.share', 'option', 'Loan Shares',
        states={'invisible': Eval('coverage_family', '') != 'loan'}, domain=[
                ('loan.parties', 'in', Eval('parties', []))],
        depends=['coverage_family', 'parties'])
    multi_mixed_view = loan_shares

    @fields.depends('coverage', 'loan_shares')
    def on_change_coverage(self):
        result = super(ContractOption, self).on_change_coverage()
        if result['coverage_family'] != 'loan':
            result['loan_shares'] = {
                'remove': [x.id for x in self.loan_shares]}
        return result


class ExtraPremium:
    __name__ = 'contract.option.extra_premium'

    capital_per_mil_rate = fields.Numeric('Rate on Capital', states={
            'invisible': Eval('calculation_kind', '') != 'capital_per_mil',
            'required': Eval('calculation_kind', '') == 'capital_per_mil'},
        digits=(16, 5), depends=['calculation_kind'])
    is_loan = fields.Function(
        fields.Boolean('Is Loan'),
        'on_change_with_is_loan')

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls.calculation_kind.selection_change_with.add('is_loan')
        cls.calculation_kind.depends.append('is_loan')
        utils.update_on_change_with(cls, 'rec_name', ['capital_per_mil_rate'])

    @classmethod
    def default_is_loan(cls):
        if 'is_loan' in Transaction().context:
            return Transaction().context.get('is_loan')
        return False

    @fields.depends('option')
    def on_change_with_is_loan(self, name=None):
        return (self.option.is_loan if self.option else
            Transaction().context.get('is_loan', False))

    def get_possible_extra_premiums_kind(self):
        result = super(ExtraPremium, self).get_possible_extra_premiums_kind()
        if self.is_loan:
            result.append(('capital_per_mil', 'Pourmillage'))
        return result

    def calculate_premium_amount(self, args, base):
        if not self.calculation_kind == 'capital_per_mil':
            return super(ExtraPremium, self).calculate_premium_amount(args,
                base)
        return args['loan'].amount * self.capital_per_mil_rate

    def get_rec_name(self, name):
        if (self.calculation_kind == 'capital_per_mil'
                and self.capital_per_mil_rate):
            return u'%s ‰' % coop_string.format_number('%.2f',
                self.capital_per_mil_rate * 1000)
        return super(ExtraPremium, self).get_rec_name(name)


class LoanShare(model.CoopSQL, model.CoopView):
    'Loan Share'

    __name__ = 'loan.share'

    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    loan = fields.Many2One('loan', 'Loan', ondelete='RESTRICT')
    share = fields.Numeric('Loan Share', digits=(16, 4))
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'on_change_with_person')
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')

    @staticmethod
    def default_share():
        return 1

    def on_change_with_icon(self, name=None):
        return 'loan-interest'

    @fields.depends('option')
    def on_change_with_person(self, name=None):
        if not self.option:
            return None
        covered_element = getattr(self.option, 'covered_element', None)
        if covered_element is None:
            return None
        return covered_element.party.id if covered_element.party else None

    def get_name_for_billing(self):
        return '%s %s%% %s' % (self.person.get_rec_name(None),
            str(self.share * 100), self.loan.get_rec_name(None))

    def init_dict_for_rule_engine(self, current_dict):
        self.loan.init_dict_for_rule_engine(current_dict)
        current_dict['share'] = self

    def get_publishing_values(self):
        result = super(LoanShare, self).get_publishing_values()
        result.update(self.loan.get_publishing_values())
        result['share'] = '%.2f %%' % (self.share * 100)
        result['covered_amount'] = self.share * result['amount']
        return result

    def get_rec_name(self, name):
        return '%s (%s%%)' % (self.loan.rec_name, self.share * 100)

    def _expand_tree(self, name):
        return True
