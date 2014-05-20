# -*- coding: utf-8 -*-
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, Bool

from trytond.modules.cog_utils import utils, fields, model, coop_string

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractOption',
    'ExtraPremium',
    'LoanShare',
    'OptionSubscription',
    'OptionsDisplayer',
    'WizardOption',
    'OptionSubscriptionWizardLauncher',
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
        if not self.is_loan:
            return
        loans = set([share.loan
                for covered_element in self.covered_elements
                for option in covered_element.options
                for share in option.loan_shares])
        if not loans:
            return
        end_date = max([x.end_date for x in loans])
        self.set_end_date(end_date)


class ContractOption:
    __name__ = 'contract.option'

    loan_shares = fields.One2Many('loan.share', 'option', 'Loan Shares',
        states={'invisible': Eval('coverage_family', '') != 'loan'}, domain=[
            ('loan.parties', 'in', Eval('parties', [])),
            ('start_date', '>=', Eval('start_date', datetime.date.min)),
            If(Bool(Eval('end_date', None)),
                [('end_date', '<=', Eval('end_date'))],
                [])],
        depends=['coverage_family', 'parties', 'start_date', 'end_date'])
    multi_mixed_view = loan_shares

    @fields.depends('coverage', 'loan_shares')
    def on_change_coverage(self):
        result = super(ContractOption, self).on_change_coverage()
        if result['coverage_family'] != 'loan':
            result['loan_shares'] = {
                'remove': [x.id for x in self.loan_shares]}
        return result

    @fields.depends('start_date', 'end_date', 'loan_shares')
    def on_change_with_loan_shares(self):
        to_update = []
        for share in self.loan_shares:
            res = {'id': share.id}
            if share.start_date < self.start_date:
                res['start_date'] = self.start_date
            if self.end_date and (not share.end_date or
                    share.end_date > self.end_date):
                res['end_date'] = self.end_date
            if len(res) > 1:
                to_update.append(res)
        if to_update:
            return {'update': to_update}

    def set_end_date(self, end_date):
        for share in self.loan_shares:
            if share.end_date and share.end_date <= end_date:
                continue
            share.end_date = end_date
        self.loan_shares = self.loan_shares


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
        return (self.option.coverage.family == 'loan' if self.option else
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
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    loan = fields.Many2One('loan', 'Loan', ondelete='RESTRICT', required=True)
    share = fields.Numeric('Loan Share', digits=(16, 4))
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'on_change_with_person')
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_contract', searcher='search_contract')

    @staticmethod
    def default_share():
        return 1

    @classmethod
    def default_start_date(cls):
        return Transaction().context.get('start_date', utils.today())

    @fields.depends('loan')
    def on_change_loan(self):
        return {'end_date': self.loan.end_date if self.loan else None}

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

    def get_contract(self, name):
        return self.option.covered_element.contract.id

    @classmethod
    def search_contract(cls, name, clause):
        return [('option.covered_element.contract', ) + tuple(clause[1:])]

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


class OptionSubscription:
    __name__ = 'contract.wizard.option_subscription'

    def default_options_displayer(self, values):
        res = super(OptionSubscription, self).default_options_displayer(values)
        res['default_share'] = 1
        return res

    @classmethod
    def init_default_options(cls, contract, subscribed_options):
        res = super(OptionSubscription, cls).init_default_options(contract,
            subscribed_options)
        res['loans'] = [x.id for x in contract.used_loans]
        return res

    @classmethod
    def init_default_childs(cls, contract, coverage, option, parent_dict):
        res = super(OptionSubscription, cls).init_default_childs(contract,
            coverage, option, parent_dict)
        for loan in contract.used_loans:
            loan_share = None
            for share in option.loan_shares if option else []:
                if share.loan == loan:
                    loan_share = share
                    break
            res.append({
                    'loan': loan.id,
                    'name': loan.rec_name,
                    'share': loan_share.share if loan_share else 1,
                    'is_selected': (loan_share is not None
                        or parent_dict['is_selected']),
                    'childs': [],
                    'selection': 'manual',
                    })
        return res


class OptionsDisplayer:
    __name__ = 'contract.wizard.option_subscription.options_displayer'

    default_share = fields.Numeric('Default Loan Share', digits=(16, 4))
    loans = fields.Many2Many('loan', None, None, 'Loans',
        domain=[('parties', '=', Eval('party'))],
        depends=['party'])

    @fields.depends('loans', 'options', 'default_share')
    def on_change_loans(self):
        res = {}
        option_dicts = []
        for option in self.options:
            loans_to_add = []
            loans_to_remove = []
            childs_dict = {}
            for loan in self.loans:
                for child in option.childs:
                    if child.loan == loan:
                        if option.is_selected:
                            childs_dict.setdefault('update', []).append({
                                    'id': child.id,
                                    'is_selected': True,
                                    })
                        break
                else:
                    loan_dict = {
                        'loan': loan.id,
                        'childs': [],
                        'name': loan.rec_name,
                        'is_selected': option.is_selected,
                        'share': self.default_share,
                        'selection': 'manual',
                        }
                    loans_to_add.append((-1, loan_dict))
            if loans_to_add:
                childs_dict['add'] = loans_to_add

            loans_to_remove = [x.id for x in option.childs
                if not x.loan in self.loans]
            if loans_to_remove:
                childs_dict.setdefault('update', [])
                childs_dict['update'] += [{'id': x, 'is_selected': False}
                    for x in loans_to_remove]
            if childs_dict:
                option_dicts.append({'id': option.id, 'childs': childs_dict})
        if option_dicts:
            res = {'options': {'update': option_dicts}}
        return res

    @fields.depends('default_share', 'options')
    def on_change_default_share(self):
        res = {'options': {'update': []}}
        for option in self.options:
            option_dict = None
            for child in option.childs:
                if not child.loan:
                    continue
                if not option_dict:
                    option_dict = {'id': option.id, 'childs': {'update': []}}
                    res['options']['update'].append(option_dict)
                option_dict['childs']['update'].append({
                        'id': child.id,
                        'share': self.default_share,
                        })
        return res

    #This will unselect loans when the option is unselected
    #and will prevent to select loans if the option is not selected
    def on_change_options(self):
        res = super(OptionsDisplayer, self).on_change_options()
        for option in self.options:
            if not option.childs or option.is_selected:
                continue
            option_dict = None
            for cur_option_dict in res.get('options', {}).get('update', []):
                if cur_option_dict['id'] == option.id:
                    option_dict = cur_option_dict
                    break
            if not option_dict:
                option_dict = {'id': option.id}
                res.setdefault('options', {}).setdefault('update', []).append(
                    option_dict)
            for child in option.childs:
                child_dict = None
                for cur_child_dict in option_dict.get('childs', {}).get(
                        'update', []):
                    if cur_child_dict['id'] == child.id:
                        child_dict = cur_child_dict
                        break
                if not child_dict:
                    child_dict = {'id': child.id}
                    option_dict.setdefault('childs',
                        {}).setdefault('update', []).append(child_dict)
                child_dict['is_selected'] = option_dict.get('is_selected',
                    option.is_selected)
        return res


class WizardOption:
    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    share = fields.Numeric('Loan Share', digits=(16, 4),
        states={'readonly': ~Eval('loan')})
    loan = fields.Many2One('loan', 'Loan')

    @fields.depends('loan')
    def on_change_with_name(self, name=None):
        if self.loan:
            return self.loan.rec_name
        else:
            return super(WizardOption, self).on_change_with_name(name)

    def update_option_if_needed(self, option):
        super(WizardOption, self).update_option_if_needed(option)
        if not getattr(self, 'loan', None):
            return
        LoanShare = Pool().get('loan.share')
        option.loan_shares = list(getattr(option, 'loan_shares', []))
        loans = [x.loan for x in option.loan_shares]
        existing_loan_share = None
        for loan_share in option.loan_shares:
            if loan_share.loan == self.loan:
                existing_loan_share = loan_share
                break
        if self.is_selected and self.parent.is_selected:
            if not self.loan in loans:
                loan_share = LoanShare()
                loan_share.loan = self.loan
                option.loan_shares.append(loan_share)
            else:
                loan_share = existing_loan_share
            loan_share.share = self.share
        elif not self.is_selected and existing_loan_share:
            option.loan_shares.remove(existing_loan_share)
            LoanShare.delete([existing_loan_share])


class OptionSubscriptionWizardLauncher:
    __name__ = 'contract.wizard.option_subscription_launcher'

    def skip_wizard(self, contract):
        for covered_element in contract.covered_elements:
            for option in covered_element.options:
                for loan_share in option.loan_shares:
                    return True
        return super(OptionSubscriptionWizardLauncher, self).skip_wizard(
            contract)
