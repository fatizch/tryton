# -*- coding: utf-8 -*-
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model, coop_string
from trytond.modules.cog_utils import coop_date

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
    'DisplayContractPremium',
    ]


class Contract:
    __name__ = 'contract'

    is_loan = fields.Function(
        fields.Boolean('Is Loan'),
        'on_change_with_is_loan')
    loans = fields.Function(
        fields.Many2Many('loan', None, None, 'Loans',
            states={
                'invisible': (~Eval('is_loan')) | (~Eval('subscriber', False)),
                'readonly': Eval('status') != 'quote',
                },
            depends=['is_loan', 'currency', 'status', 'subscriber', 'parties'],
            context={
                'currency': Eval('currency'),
                'parties': Eval('parties'),
                }),
        'on_change_with_loans', 'set_loans')
    used_loans = fields.Function(
        fields.Many2Many('loan', None, None, 'Used Loans',
            context={'contract': Eval('id')}, depends=['id']),
        'get_used_loans')

    def get_used_loans(self, name):
        loans = set([share.loan
            for covered_element in self.covered_elements
            for option in covered_element.options
            for share in option.loan_shares])

        return [x.id for x in sorted(list(loans), key=lambda x: x.id)]

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

    def set_contract_end_date_from_loans(self):
        if not self.is_loan:
            return
        loans = set([share.loan
                for covered_element in self.covered_elements
                for option in covered_element.options
                for share in option.loan_shares])
        if not loans:
            return
        end_date = coop_date.add_day(max([x.end_date for x in loans]), -1)
        self.set_end_date(end_date, force=True)

    @classmethod
    def set_loans(cls, instances, name, vals):
        Loan = Pool().get('loan')
        for val in vals:
            if val[0] == 'create':
                Loan.create(val[1])
            elif val[0] == 'write':
                values = val[1:]
                for i, x in enumerate(values):
                    if i % 2 == 0:
                        values[i] = [Loan(x[0])]
                Loan.write(*values)
            elif val[0] == 'delete':
                Loan.delete([Loan(x) for x in val[1]])


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

    @fields.depends('start_date', 'end_date', 'loan_shares')
    def on_change_with_loan_shares(self):
        to_update = []
        for share in self.loan_shares:
            res = {'id': share.id}
            if share.start_date or datetime.date.min < self.start_date:
                res['start_date'] = self.start_date
            if self.end_date and (not share.end_date or
                    share.end_date > self.end_date):
                res['end_date'] = self.end_date
            if len(res) > 1:
                to_update.append(res)
        if to_update:
            return {'update': to_update}

    @classmethod
    def set_end_date(cls, options, name, end_date):
        super(ContractOption, cls).set_end_date(options, name, end_date)
        for option in options:
            if end_date:
                for share in option.loan_shares:
                    if share.end_date and share.end_date <= end_date:
                        continue
                    # TEMP fix before removing start_date/end_date from share
                    share.end_date = min(end_date, share.loan.end_date)
            option.loan_shares = option.loan_shares
            option.save()


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
    def default_is_loan(cls):
        if 'is_loan' in Transaction().context:
            return Transaction().context.get('is_loan')
        return False

    @fields.depends('option')
    def on_change_with_is_loan(self, name=None):
        return (self.option.coverage.family == 'loan' if self.option else
            Transaction().context.get('is_loan', False))

    @fields.depends('is_loan')
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

    @fields.depends('capital_per_mil_rate')
    def on_change_with_rec_name(self, name=None):
        return super(ExtraPremium, self).on_change_with_rec_name(name)


class LoanShare(model.CoopSQL, model.CoopView, model.ExpandTreeMixin):
    'Loan Share'

    __name__ = 'loan.share'

    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE',
        required=True, select=1)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    loan = fields.Many2One('loan', 'Loan', ondelete='RESTRICT', required=True,
        domain=[('state', '=', 'calculated')])
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

    @classmethod
    def init_default_childs(cls, contract, coverage, option, parent_dict):
        res = super(OptionSubscription, cls).init_default_childs(contract,
            coverage, option, parent_dict)
        for loan in contract.loans:
            loan_share = None
            for share in option.loan_shares if option else []:
                if share.loan == loan:
                    loan_share = share
                    break
            res.append({
                    'loan': loan.id,
                    'share': loan_share.share if loan_share else 1,
                    'is_selected': (loan_share is not None
                        or parent_dict['is_selected']),
                    'selection': 'manual',
                    })
        return res

    def add_remove_options(self, options, lines):
        super(OptionSubscription, self).add_remove_options(options,
            [x for x in lines if getattr(x, 'coverage', None)])
        for line in lines:
            if getattr(line, 'coverage', None):
                parent = line
                continue
            line.update_loan_shares(parent.option, parent)


class OptionsDisplayer:
    __name__ = 'contract.wizard.option_subscription.options_displayer'

    default_share = fields.Numeric('Default Loan Share', digits=(16, 4))

    @fields.depends('default_share', 'options')
    def on_change_default_share(self):
        update_list = []
        for line in [x for x in self.options if getattr(x, 'loan', None)]:
            update_list.append({
                    'id': line.id,
                    'share': self.default_share,
                    })
        return {'options': {'update': update_list}}

    # This will unselect loans when the option is unselected
    # and will prevent to select loans if the option is not selected
    def on_change_options(self):
        changes = super(OptionsDisplayer, self).on_change_options()
        update_list = []
        for line in self.options:
            if not getattr(line, 'loan', None):
                parent = line
                continue
            if line.is_selected and not parent.is_selected:
                update_list = changes.setdefault('options', {}).setdefault(
                    'update', [])
                update_list.append(
                    {'id': line.id, 'is_selected': parent.is_selected})
        return changes


class WizardOption:
    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    share = fields.Numeric('Loan Share', digits=(16, 4),
        states={'readonly': ~Eval('loan')})
    loan = fields.Many2One('loan', 'Loan')

    @fields.depends('loan')
    def on_change_with_name(self, name=None):
        if self.loan:
            return '    %s' % self.loan.rec_name
        else:
            return super(WizardOption, self).on_change_with_name(name)

    def update_loan_shares(self, option, parent):
        if option is None:
            return
        LoanShare = Pool().get('loan.share')
        option.loan_shares = list(getattr(option, 'loan_shares', []))
        loans = [x.loan for x in option.loan_shares]
        existing_loan_share = None
        for loan_share in option.loan_shares:
            if loan_share.loan == self.loan:
                existing_loan_share = loan_share
                break
        if self.is_selected and parent.is_selected:
            if self.loan not in loans:
                loan_share = LoanShare()
                loan_share.loan = self.loan
                option.loan_shares.append(loan_share)
                loan_share.share = self.share
                option.save()
            else:
                loan_share = existing_loan_share
                loan_share.share = self.share
                loan_share.save()
        elif not self.is_selected and existing_loan_share:
            option.loan_shares.remove(existing_loan_share)
            LoanShare.delete([existing_loan_share])
            option.save()


class OptionSubscriptionWizardLauncher:
    __name__ = 'contract.wizard.option_subscription_launcher'

    def skip_wizard(self, contract):
        for covered_element in contract.covered_elements:
            for option in covered_element.options:
                for loan_share in option.loan_shares:
                    return True
        return super(OptionSubscriptionWizardLauncher, self).skip_wizard(
            contract)


class DisplayContractPremium:
    __name__ = 'contract.premium.display'

    @classmethod
    def new_line(cls, line=None):
        new_line = super(DisplayContractPremium, cls).new_line(line)
        if not line or not line.loan:
            return new_line
        new_line['name'] = '[%s] %s' % (line.loan.number, new_line['name'])
        return new_line
