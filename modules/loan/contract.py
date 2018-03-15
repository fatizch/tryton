# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import defaultdict
from decimal import Decimal

from sql import Literal
from sql.conditionals import Coalesce

from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If, Len, Not, In

from trytond.modules.coog_core import fields, model, coog_string, coog_date, \
    utils

__all__ = [
    'Contract',
    'ContractLoan',
    'ContractOption',
    'ExtraPremium',
    'LoanShare',
    'OptionSubscription',
    'OptionsDisplayer',
    'WizardOption',
    'DisplayContractPremium',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    is_loan = fields.Function(
        fields.Boolean('Is Loan'),
        'on_change_with_is_loan')
    loans = fields.Many2Many('contract-loan', 'contract', 'loan', 'Loans',
        states={
            'invisible': (~Eval('is_loan') | ~Eval('subscriber', False)
                | Bool(Eval('show_ordered_loans'))),
            'readonly': Eval('status') != 'quote',
            },
        context={
            'contract': Eval('id'),
            'start_date': Eval('start_date'),
            'nb_of_loans': Len(Eval('loans', [])),
            },
        depends=['is_loan', 'status', 'id', 'show_ordered_loans',
            'start_date'])
    show_ordered_loans = fields.Function(
        fields.Boolean('Show Ordered Loans',
            states={
                'invisible': ~Eval('is_loan'),
                'readonly': Eval('status') != 'quote',
                }),
        'get_show_ordered_loans', 'setter_void')
    ordered_loans = fields.One2Many('contract-loan', 'contract',
        'Ordered Loans',
        states={
            'invisible': (~Eval('is_loan') | ~Eval('subscriber', False)
                | ~Eval('show_ordered_loans')),
            'readonly': Eval('status') != 'quote',
            },
        depends=['is_loan', 'status'], delete_missing=True)
    used_loans = fields.Function(
        fields.Many2Many('loan', None, None, 'Used Loans',
            context={'contract': Eval('id')}, depends=['id']),
        'get_used_loans')
    shares_per_loan = fields.Function(
        fields.Many2Many('loan.share', None, None, 'Shares per Loan',
            context={'contract': Eval('id')}),
        'get_shares_per_loan')

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
        cls._error_messages.update({
                'no_loan_on_contract': 'There must be at least one loan',
                'no_loan_on_option': 'At least one loan must be '
                'selected for %s',
                'loan_not_calculated': 'Loan %s must be calculated before'
                ' proceeding',
                'no_option_for_loan': 'Loan %s does not have an option',
                'bad_loan_dates': 'Loans fund release dates should be synced '
                'with the contract start date :\n\n\t%s',
                })

    @classmethod
    def write(cls, contracts, values, *args):
        super(Contract, cls).write(contracts, values, *args)
        ContractLoan = Pool().get('contract-loan')
        to_write = []
        for contract in contracts:
            for i, loan in enumerate(contract.ordered_loans, 1):
                if not loan.number or contract.status == 'quote':
                    to_write += [[loan], {'number': i}]
        if to_write:
            ContractLoan.write(*to_write)

    def get_used_loans(self, name):
        return [x.id for x in self.get_used_loans_at_date(utils.today())]

    def get_used_loans_at_date(self, at_date):
        return sorted(list(set([x.loan
                        for covered_element in self.covered_elements
                        for option in covered_element.options
                        for x in option.get_shares_at_date(at_date)
                        if x.share])),
            key=lambda x: x.id)

    def get_show_ordered_loans(self, name):
        return False

    @fields.depends('product')
    def on_change_product(self):
        super(Contract, self).on_change_product()
        self.is_loan = self.product.is_loan if self.product else False
        if not self.is_loan:
            self.loans = []

    @fields.depends('product')
    def on_change_with_is_loan(self, name=None):
        return self.product.is_loan if self.product else False

    def get_shares_per_loan(self, name=None):
        with Transaction().set_context(contract=self.id):
            per_loan = defaultdict(list)
            [per_loan[share.loan].append(share)
                for covered_element in self.covered_elements
                for option in covered_element.options
                for share in option.loan_shares]
            return [share.id
                for loan in sorted(per_loan.keys(), key=lambda x: x.order)
                for share in per_loan[loan]]

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    @classmethod
    def _ws_import_entity(cls, item):
        if item['__name__'] == 'loan':
            loan = Pool().get('loan').import_json(item)
            loan.calculate()
            loan.save()
            return [{'loan_number': loan.number}]
        return super(Contract, cls)._ws_import_entity(item)

    @staticmethod
    def default_show_ordered_loans():
        return False

    @classmethod
    def _calculate_methods(cls, product):
        return [('options', 'remove_unneeded_loan_share')] + super(Contract,
            cls)._calculate_methods(product)

    def check_contract_loans(self):
        if not self.loans:
            self.append_functional_error('no_loan_on_contract')
        for loan in self.loans:
            if not loan.state == 'calculated':
                self.append_functional_error('loan_not_calculated', (
                        loan.rec_name))

    def check_no_option_without_loan(self):
        for covered in self.covered_elements:
            for option in covered.options:
                if option.coverage.is_loan and not \
                        option.check_at_least_one_loan():
                    self.append_functional_error('no_loan_on_option',
                        (option.get_rec_name('')))

    def check_no_loan_without_option(self):
        orphans = set(self.loans) - set(self.used_loans)
        if not orphans:
            return
        for orphan in orphans:
            self.append_functional_error('no_option_for_loan',
                (orphan.rec_name,))

    def check_loan_dates(self):
        bad_loans = [x for x in self.loans
            if x.funds_release_date != self.initial_start_date]
        if bad_loans:
            self.raise_user_warning(self.rec_name, 'bad_loan_dates',
                ('\t\n'.join(x.rec_name for x in bad_loans),))

    def get_show_premium(self, name):
        if not self.is_loan:
            return super(Contract, self).get_show_premium(name)
        return False


class ContractLoan(model.CoogSQL, model.CoogView):
    'Contract Loan'

    __name__ = 'contract-loan'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE', select=True)
    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE', required=True,
        select=True)
    number = fields.Integer('Number')
    loan_state = fields.Function(
        fields.Char('Loan State'),
        'on_change_with_loan_state')

    @classmethod
    def __setup__(cls):
        super(ContractLoan, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))

    def get_func_key(self, name):
        return '|'.join([self.contract.contract_number, str(self.number)])

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                contract_number, loan_order = operands
                if contract_number == 'None':
                    contract_number = None
                return [
                    ('contract.contract_number', '=', contract_number),
                    ('number', '=', int(loan_order)),
                    ]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('contract.contract_number',) + tuple(clause[1:])],
                [('number', clause[1], str(clause[2]))],
                ]

    @fields.depends('loan')
    def on_change_with_loan_state(self, name=None):
        return self.loan.state if self.loan else ''


class ContractOption:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    is_loan = fields.Function(
        fields.Boolean('Loan'),
        'get_is_loan')
    loan_shares = fields.One2Many('loan.share', 'option', 'Loan Shares',
        states={
            'invisible': Eval('coverage_family', '') != 'loan',
            },
        depends=['coverage_family', 'contract_status'], readonly=True,
        delete_missing=True)
    latest_loan_shares = fields.Function(
        fields.One2Many('loan.share', 'option', 'Loan Shares', states={
            'invisible': Eval('coverage_family', '') != 'loan',
            }, depends=['coverage_family']),
        'get_latest_loan_shares')
    multi_mixed_view = latest_loan_shares

    @classmethod
    def _export_skips(cls):
        return (super(ContractOption, cls)._export_skips() |
            set(['multi_mixed_view']))

    @fields.depends('coverage', 'loan_shares', 'is_loan')
    def on_change_coverage(self):
        super(ContractOption, self).on_change_coverage()
        if not self.is_loan:
            self.loan_shares = []

    def get_is_loan(self, name):
        return self.coverage_family == 'loan'

    def get_latest_loan_shares(self, name):
        all_shares_per_loan = self.get_shares_per_loan()
        shares = [all_shares_per_loan[loan.loan.id][-1]
            for loan in self.parent_contract.ordered_loans
            if loan.loan.id in all_shares_per_loan]
        active_loans = [x.loan.id for x in shares]
        for loan_id, cur_shares in all_shares_per_loan.items():
            if loan_id in active_loans:
                continue
            shares.append(cur_shares[-1])
        return [x.id for x in self._sort_latest_loan_shares(shares)]

    def _sort_latest_loan_shares(self, shares):
        return sorted(shares, key=lambda x: x.loan.number)

    def get_shares_at_date(self, at_date, include_removed=False):
        shares = []
        current_loans = {x.loan.id: x.number
            for x in self.parent_contract.ordered_loans}
        for loan, cur_shares in self.get_shares_per_loan().items():
            if not include_removed and loan not in current_loans:
                continue
            for share in reversed(cur_shares):
                if (getattr(share, 'start_date', None)
                        or datetime.date.min) <= at_date:
                    shares.append(share)
                    break
        shares.sort(key=lambda x: (x.loan.id in current_loans,
                current_loans.get(x.loan.id, None)))
        return shares

    def get_shares_per_loan(self):
        result = defaultdict(list)
        for share in sorted(self.loan_shares,
                key=lambda x: getattr(x, 'start_date', None)
                or datetime.date.min):
            result[share.loan.id].append(share)
        return result

    def get_possible_end_date(self):
        dates = super(ContractOption, self).get_possible_end_date()
        if self.coverage_family != 'loan':
            return dates
        if self.loan_shares:
            # Loan shares are sorted per date, so x[-1] to get the latest one,
            # and if the share is 0 (the loan is no longer covered), we use the
            # share date rather than the loan's end date
            date_max = max([
                    x[-1].loan.end_date if x[-1].share else
                    coog_date.add_day(x[-1].start_date, -1)
                    for x in self.get_shares_per_loan().values()])

            if date_max:
                dates['loan'] = date_max
        return dates

    def calculate_automatic_end_date(self):
        calculated_date = super(ContractOption,
            self).calculate_automatic_end_date()
        if not self.loan_shares:
            return calculated_date
        max_loan = max([x.loan.end_date for x in self.loan_shares])
        return min(calculated_date, max_loan) if calculated_date else max_loan

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

    def remove_unneeded_loan_share(self):
        LoanShare = Pool().get('loan.share')
        loan_shares_to_delete = [x for x in self.loan_shares
            if x.loan not in self.parent_contract.loans]
        LoanShare.delete(loan_shares_to_delete)

    def check_at_least_one_loan(self):
        return True if self.loan_shares else False

    def get_insured_outstanding_loan_balance(self, date):
        if not self.is_loan or not self.covered_element.party:
            return Decimal(0)
        party = self.covered_element.party
        return party.get_insured_outstanding_loan_balances(date,
            self.coverage.currency, self.coverage.insurer,
            self.coverage.insurance_kind
            )[self.coverage.insurer.id][self.coverage.insurance_kind][0]

    def get_option_loan_balance(self, date):
        # Total loan insured on this option
        return (sum([l.get_outstanding_loan_balance(date)
                    for l in self.loan_shares])
            if self.status not in ['declined', 'void'] else Decimal(0))

    def get_total_loan_balance(self, date):
        # Returns total amount on current option and other loans
        outstanding = self.get_insured_outstanding_loan_balance(date)
        if self.status == 'active' and self.parent_contract.status == 'active':
            # When contract and option is active
            # get_insured_outstanding_loan_balance
            # returns also current option outstanding loans amount
            return outstanding
        else:
            return outstanding + self.get_option_loan_balance(date)


class ExtraPremium:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.extra_premium'

    capital_per_mil_rate = fields.Numeric('Rate on Capital', states={
            'invisible': Not(In(Eval('calculation_kind', ''), [
                        'initial_capital_per_mil',
                        'remaining_capital_per_mil'])),
            'required': In(Eval('calculation_kind', ''), [
                    'initial_capital_per_mil',
                    'remaining_capital_per_mil'])},
        digits=(16, 5), depends=['calculation_kind'])
    is_loan = fields.Function(
        fields.Boolean('Is Loan'),
        'on_change_with_is_loan')

    @classmethod
    def __setup__(cls):
        super(ExtraPremium, cls).__setup__()
        cls._error_messages.update({
                'initial_capital_per_mil_label': 'Initial Capital Per Mil',
                'remaining_capital_per_mil_label': 'Remaining Capital Per Mil',
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()

        super(ExtraPremium, cls).__register__(module_name)

        # Migration from 1.4 : Convert 'capital_per_mil' to
        # 'initial_capital_per_mil'
        extra_table = cls.__table__()
        cursor.execute(*extra_table.update(
                columns=[extra_table.calculation_kind],
                values=[Literal('initial_capital_per_mil')],
                where=(extra_table.calculation_kind == 'capital_per_mil')))

    @classmethod
    def view_attributes(cls):
        return super(ExtraPremium, cls).view_attributes() + [(
                '/form/group[@id="capital_per_mil"]', 'states',
                {'invisible': Not(In(Eval('calculation_kind'),
                            ['initial_capital_per_mil',
                                'remaining_capital_per_mil']))})]

    @fields.depends('option')
    def on_change_with_is_loan(self, name=None):
        return self.option.coverage.family == 'loan' if self.option else False

    @fields.depends('is_loan')
    def get_possible_extra_premiums_kind(self):
        result = super(ExtraPremium, self).get_possible_extra_premiums_kind()
        if self.is_loan:
            result.append(('initial_capital_per_mil',
                    self.raise_user_error('initial_capital_per_mil_label',
                        raise_exception=False)))
            result.append(('remaining_capital_per_mil',
                    self.raise_user_error('remaining_capital_per_mil_label',
                        raise_exception=False)))
        return result

    def calculate_premium_amount(self, args, base):
        if self.calculation_kind == 'initial_capital_per_mil':
            if args['share'].loan.end_date <= args['date']:
                return 0
            return args['loan'].amount * self.capital_per_mil_rate * \
                args['share'].share
        elif self.calculation_kind == 'remaining_capital_per_mil':
            if args['share'].loan.end_date <= args['date']:
                return 0
            return args['loan'].get_outstanding_loan_balance(
                at_date=args['date']) * self.capital_per_mil_rate * \
                args['share'].share
        else:
            return super(ExtraPremium, self).calculate_premium_amount(args,
                base)

    def get_value_as_string(self, name):
        if self.calculation_kind in ('initial_capital_per_mil',
                'remaining_capital_per_mil') and self.capital_per_mil_rate:
            return u'%s ‰' % coog_string.format_number('%.2f',
                self.capital_per_mil_rate * 1000)
        return super(ExtraPremium, self).get_value_as_string(name)

    @fields.depends('capital_per_mil_rate', 'calculation_kind')
    def on_change_with_value_as_string(self, name=None):
        return self.get_value_as_string(name)


_STATES = {
    'readonly': Eval('_parent_contract', {}).get('status', '') != 'quote'}
_DEPENDS = ['contract']


class LoanShare(model.CoogSQL, model.CoogView, model.ExpandTreeMixin):
    'Loan Share'

    __name__ = 'loan.share'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    option = fields.Many2One('contract.option', 'Option', ondelete='CASCADE',
        required=True, select=True, states=_STATES, depends=_DEPENDS)
    start_date = fields.Date('Start Date', states=_STATES, depends=_DEPENDS)
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_end_date')
    loan = fields.Many2One('loan', 'Loan', ondelete='RESTRICT', required=True,
        domain=[('state', '=', 'calculated')], states=_STATES,
        depends=_DEPENDS)
    share = fields.Numeric('Loan Share', digits=(16, 4),
        domain=[('share', '>=', 0), ('share', '<=', 1)],
        states=_STATES, depends=_DEPENDS)
    person = fields.Function(
        fields.Many2One('party.party', 'Person'),
        'on_change_with_person', searcher='search_person')
    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')
    contract = fields.Function(
        fields.Many2One('contract', 'Contract'),
        'get_contract', searcher='search_contract')

    @classmethod
    def __setup__(cls):
        super(LoanShare, cls).__setup__()
        cls._order = [('loan', 'ASC'), ('start_date', 'ASC')]

    @classmethod
    def __register__(cls, module_name):
        super(LoanShare, cls).__register__(module_name)
        # Migration from 1.3: Drop end_date column
        TableHandler = backend.get('TableHandler')
        share_table = TableHandler(cls)
        if share_table.column_exist('end_date'):
            share_table.drop_column('end_date')

    def get_func_key(self, name):
        return '|'.join([self.loan.number, str(self.start_date)])

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                loan_number, share_date = operands
                if share_date == 'None':
                    share_date = None
                else:
                    share_date = datetime.datetime.strptime(share_date,
                        '%y-%m-%d').date()
                return [
                    ('loan.number', '=', loan_number),
                    ('start_date', '=', share_date),
                    ]
            else:
                return [('id', '=', None)]
        else:
            raise NotImplementedError

    @staticmethod
    def default_share():
        return 1

    @fields.depends('end_date', 'option', 'share', 'start_date')
    def on_change_with_icon(self, name=None):
        if self.share == 0 or self.option and self.option.status in [
                'terminated', 'void']:
            return 'loan-interest-grey-cancel'
        elif (self.start_date or datetime.date.min) <= utils.today() <= (
                self.end_date or datetime.date.max):
            return 'loan-interest-green'
        elif self.end_date and utils.today() > self.end_date:
            return 'loan-interest-grey-cancel'
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

    def get_end_date(self, name):
        if self.option.status in ['void', 'declined']:
            return None
        for share in sorted(self.option.loan_shares, key=lambda x: (x.loan.id,
                    x.start_date or datetime.date.min)):
            if share == self:
                continue
            if self.loan.id != share.loan.id:
                continue
            if (self.start_date or datetime.date.min) > (share.start_date or
                    datetime.date.min):
                continue
            # First loan share for the same loan but "older":
            return min(self.option.end_date,
                coog_date.add_day(share.start_date, -1))
        else:
            return min(self.option.end_date, self.get_insured_loan_end_date())

    def get_insured_loan_end_date(self):
        # Used for clients who want to override the default behaviour and want
        # the contract to end the day before the last payment date
        return self.loan.end_date

    @staticmethod
    def order_start_date(tables):
        table, _ = tables[None]
        return [Coalesce(table.start_date, datetime.date.min)]

    @classmethod
    def search_contract(cls, name, clause):
        return [('option.covered_element.contract', ) + tuple(clause[1:])]

    @classmethod
    def search_person(cls, name, clause):
        return [('option.covered_element.party',) + tuple(clause[1:])]

    def init_dict_for_rule_engine(self, current_dict):
        self.loan.init_dict_for_rule_engine(current_dict)
        self.option.init_dict_for_rule_engine(current_dict)
        current_dict['share'] = self

    def get_publishing_values(self):
        result = super(LoanShare, self).get_publishing_values()
        result.update(self.loan.get_publishing_values())
        result['share'] = '%.2f %%' % (self.share * 100)
        result['covered_amount'] = self.share * result['amount']
        return result

    def get_rec_name(self, name):
        with Transaction().set_context(contract=self.contract.id if
                self.contract else None):
            return '%s (%s%%)' % (self.loan.rec_name, self.share * 100)

    def get_outstanding_loan_balance(self, at_date=None):
        if not at_date:
            at_date = self.loan.first_payment_date
        return self.loan.currency.round(self.share * (
                self.loan.get_outstanding_loan_balance(at_date=at_date) or 0))

    def _expand_tree(self, name):
        return True


class OptionSubscription:
    __metaclass__ = PoolMeta
    __name__ = 'contract.wizard.option_subscription'

    def default_options_displayer(self, values):
        res = super(OptionSubscription, self).default_options_displayer(values)
        contract = self.get_contract()
        res['is_loan'] = contract.is_loan if contract else False
        return res

    def add_remove_options(self, options, lines):
        updated_options = super(OptionSubscription, self).add_remove_options(
            options, [x for x in lines if getattr(x, 'coverage', None)])
        for line in lines:
            if getattr(line, 'coverage', None):
                parent = line
                continue
            if parent.option in updated_options:
                line.update_loan_shares(parent.option, parent)
        return updated_options


class OptionsDisplayer:
    __metaclass__ = PoolMeta
    __name__ = 'contract.wizard.option_subscription.options_displayer'

    is_loan = fields.Boolean('Is Loan')
    default_share = fields.Numeric('Default Loan Share', digits=(16, 4),
        domain=['OR',
            [('default_share', '=', None)],
            [('default_share', '>', 0), ('default_share', '<=', 1)],
            ], states={'invisible': ~Eval('is_loan')})

    @classmethod
    def view_attributes(cls):
        return super(OptionsDisplayer, cls).view_attributes() + [(
                '//label[@id="percent"]',
                'states',
                {'invisible': ~Eval('is_loan')}
                )]

    @fields.depends('default_share', 'options')
    def on_change_default_share(self):
        for option in self.options:
            if not getattr(option, 'loan', None):
                continue
            option.share = self.default_share
        self.options = self.options

    # This will unselect loans when the option is unselected
    # and will prevent to select loans if the option is not selected
    def on_change_options(self):
        super(OptionsDisplayer, self).on_change_options()
        for option in self.options:
            if not getattr(option, 'loan', None):
                parent = option
                continue
            if option.is_selected and not parent.is_selected:
                option.is_selected = parent.is_selected
        self.options = self.options

    def update_sub_options(self, new_option):
        Displayer = Pool().get(
            'contract.wizard.option_subscription.options_displayer.option')
        res = super(OptionsDisplayer, self).update_sub_options(new_option)
        for ordered_loan in [x for x in self.contract.ordered_loans]:
            loan_share = None
            loan = ordered_loan.loan
            for share in (new_option.option.loan_shares
                    if new_option.option else []):
                if share.loan == loan:
                    loan_share = share
                    break
            res.append(Displayer(loan=loan, order=ordered_loan.number,
                    share=loan_share.share if loan_share else 1,
                    is_selected=(self.options and loan_share is not None
                            or new_option.is_selected),
                    selection='manual',
                    name='    %s %s' % (ordered_loan.number, loan.rec_name),
                    ))
        return res


class WizardOption:
    __metaclass__ = PoolMeta
    __name__ = 'contract.wizard.option_subscription.options_displayer.option'

    share = fields.Numeric('Loan Share', digits=(16, 4),
        domain=[If(Bool(Eval('loan', None)),
                [('share', '>', 0), ('share', '<=', 1)],
                [])],
        states={
            'readonly': ~Eval('loan'),
            'invisible': ~Eval('_parent_displayer', {}).get('is_loan'),
            },
        depends=['loan'])
    loan = fields.Many2One('loan', 'Loan')
    order = fields.Integer('Order')

    @classmethod
    def view_attributes(cls):
        return super(WizardOption, cls).view_attributes() + [
            ('/tree', 'colors', If(~Eval('loan'), 'black', 'blue')),
            ]

    def update_loan_shares(self, option, parent):
        if option is None:
            return
        LoanShare = Pool().get('loan.share')
        loan_shares = list(getattr(option, 'loan_shares', []))
        loans = [x.loan for x in loan_shares]
        existing_loan_share = None
        for loan_share in loan_shares:
            if loan_share.loan == self.loan:
                existing_loan_share = loan_share
                break
        if self.is_selected and parent.is_selected:
            if self.loan not in loans:
                loan_share = LoanShare()
                loan_share.loan = self.loan
                loan_shares.append(loan_share)
                loan_share.share = self.share
            else:
                loan_share = existing_loan_share
                loan_share.share = self.share
        elif not self.is_selected and existing_loan_share:
            loan_shares.remove(existing_loan_share)
            LoanShare.delete([existing_loan_share])
        option.loan_shares = loan_shares
        if option.id:
            option.save()


class DisplayContractPremium:
    __metaclass__ = PoolMeta
    __name__ = 'contract.premium.display'

    def new_line(self, name, line=None):
        new_line = super(DisplayContractPremium, self).new_line(name, line)
        if not line or not line.loan:
            return new_line
        new_line['name'] = '[%s] %s' % (line.loan.number, new_line['name'])
        return new_line
