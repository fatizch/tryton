# -*- coding: utf-8 -*-
import copy

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, Or

from trytond.modules.cog_utils import utils, fields, model, coop_string

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    'CoveredData',
    'ExtraPremium',
    ]


class Contract:
    __name__ = 'contract'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')
    change_loans_order = fields.Function(
        fields.Boolean('Change Order', states={'invisible': ~Eval('is_loan')}),
        'get_change_loans_order', 'setter_void')
    loans = fields.Many2Many('contract-loan', 'contract', 'loan', 'Loans',
        states={
            'invisible': Or(~Eval('is_loan'), ~~Eval('change_loans_order')),
            }, depends=['is_loan', 'currency'],
        context={'currency': Eval('currency')})
    loans_ordered = fields.One2Many('contract-loan', 'contract', 'Loans',
        states={
            'invisible': Or(~Eval('is_loan'), ~Eval('change_loans_order')),
            }, depends=['is_loan', 'currency'],
        context={'currency': Eval('currency')})

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({'create_loan': {}})

    def get_is_loan(self, name):
        if not self.options and self.offered:
            return self.offered.is_loan
        for option in self.options:
            if option.is_loan:
                return True
        return False

    @classmethod
    @model.CoopView.button_action('loan.launch_loan_creation_wizard')
    def create_loan(cls, loans):
        pass

    def set_contract_end_date_from_loans(self):
        if not self.loans:
            return
        end_date = max([x.end_date for x in self.loans])
        self.end_date = end_date

    def get_change_loans_order(self, name):
        return False


class ContractOption:
    __name__ = 'contract.option'

    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')

    def get_is_loan(self, name=None):
        return self.offered and self.offered.family == 'loan'


class CoveredData:
    __name__ = 'contract.covered_data'

    loan_shares = fields.One2Many('loan.share', 'covered_data', 'Loan Shares',
        states={'invisible': ~Eval('is_loan')}, domain=[
            ('loan.contracts', '=', Eval('contract'))],
        depends=['contract'])
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'get_person')
    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')
    multi_mixed_view = loan_shares

    @classmethod
    def __setup__(cls):
        super(CoveredData, cls).__setup__()
        cls.extra_premiums = copy.copy(cls.extra_premiums)
        cls.extra_premiums.context['is_loan'] = ~~Eval('is_loan')

    def get_person(self, name=None):
        if self.covered_element and self.covered_element.party:
            return self.covered_element.party.id

    def init_from_option(self, option):
        super(CoveredData, self).init_from_option(option)
        LoanShare = Pool().get('loan.share')
        if not hasattr(self, 'loan_shares'):
            self.loan_shares = []
        for loan in option.contract.loans:
            share = LoanShare()
            share.loan = loan
            share.init_from_option(option)
            self.loan_shares.append(share)

    def get_is_loan(self, name):
        return self.option and self.option.is_loan


class ExtraPremium:
    __name__ = 'contract.covered_data.extra_premium'

    capital_per_mil_rate = fields.Numeric('Rate on Capital', states={
            'invisible': Eval('calculation_kind', '') != 'capital_per_mil',
            'required': Eval('calculation_kind', '') == 'capital_per_mil'},
        digits=(16, 5))
    is_loan = fields.Function(
        fields.Boolean('Is Loan', states={'invisible': True}),
        'get_is_loan')

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls.calculation_kind = copy.copy(cls.calculation_kind)
        cls.calculation_kind.selection_change_with.add('is_loan')
        cls.calculation_kind.depends.append('is_loan')

        utils.update_on_change_with(cls, 'rec_name', ['capital_per_mil_rate'])

    @classmethod
    def default_is_loan(cls):
        if 'is_loan' in Transaction().context:
            return Transaction().context.get('is_loan')
        return False

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

    def get_is_loan(self, name):
        return self.covered_data and self.covered_data.is_loan

    def get_rec_name(self, name):
        if (self.calculation_kind == 'capital_per_mil'
                and self.capital_per_mil_rate):
            return u'%s ‰' % coop_string.format_number('%.2f',
                self.capital_per_mil_rate * 1000)
        return super(ExtraPremium, self).get_rec_name(name)
