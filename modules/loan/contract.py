# -*- coding: utf-8 -*-
import datetime
from collections import defaultdict

from sql.conditionals import Coalesce

from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If, Len

from trytond.modules.cog_utils import fields, model, coop_string, coop_date, \
    utils

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    'ContractLoan',
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

    def get_show_premium(self, name):
        if not self.is_loan:
            return super(Contract, self).get_show_premium(name)
        return False


class ContractLoan(model.CoopSQL, model.CoopView):
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

    @fields.depends('start_date', 'end_date', 'loan_shares')
    def on_change_with_loan_shares(self):
        to_update = []
        for share in self.loan_shares:
            res = {'id': share.id}
            if share.start_date or datetime.date.min < self.start_date:
                res['start_date'] = self.start_date
            if len(res) > 1:
                to_update.append(res)
        if to_update:
            return {'update': to_update}

    def get_is_loan(self, name):
        return self.coverage_family == 'loan'

    def get_latest_loan_shares(self, name):
        return [x[-1].id for x in self.get_shares_per_loan().itervalues()]

    def get_shares_at_date(self, at_date):
        result = []
        for shares in self.get_shares_per_loan().itervalues():
            for share in reversed(shares):
                if not share.start_date or share.start_date <= at_date:
                    result.append(share)
                    break
        return result

    def get_shares_per_loan(self):
        result = defaultdict(list)
        for share in sorted(self.loan_shares,
                key=lambda x: x.start_date or datetime.date.min):
            result[share.loan.id].append(share)
        return result

    def get_possible_end_date(self):
        dates = super(ContractOption, self).get_possible_end_date()
        if self.coverage_family != 'loan':
            return dates
        if self.loan_shares:
            dates['loan'] = max([x.loan.end_date for x in self.loan_shares])
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
    def view_attributes(cls):
        return super(ExtraPremium, cls).view_attributes() + [(
                '/form/group[@id="capital_per_mil"]', 'states',
                {'invisible': Eval('calculation_kind') != 'capital_per_mil'})]

    @fields.depends('option')
    def on_change_with_is_loan(self, name=None):
        return self.option.coverage.family == 'loan'

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
        if args['share'].loan.end_date <= args['date']:
            return 0
        return args['loan'].amount * self.capital_per_mil_rate * \
            args['share'].share

    def get_value_as_string(self, name):
        if (self.calculation_kind == 'capital_per_mil'
                and self.capital_per_mil_rate):
            return u'%s ‰' % coop_string.format_number('%.2f',
                self.capital_per_mil_rate * 1000)
        return super(ExtraPremium, self).get_value_as_string(name)

    @fields.depends('capital_per_mil_rate', 'calculation_kind')
    def on_change_with_value_as_string(self, name=None):
        return self.get_value_as_string(name)


_STATES = {
    'readonly': Eval('_parent_contract', {}).get('status', '') != 'quote'}
_DEPENDS = ['contract']


class LoanShare(model.CoopSQL, model.CoopView, model.ExpandTreeMixin):
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
        domain=[('share', '>', 0), ('share', '<=', 1)],
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
        cursor = Transaction().cursor
        share_table = TableHandler(cursor, cls)
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

    def get_end_date(self, name):
        if self.option.status == 'void':
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
                coop_date.add_day(share.start_date, -1))
        else:
            return min(self.option.end_date, self.loan.end_date)

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

    def get_name_for_billing(self):
        return '%s %s%% %s' % (self.person.get_rec_name(None),
            str(self.share * 100), self.loan.get_rec_name(None))

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
        return '%s (%s%%)' % (self.loan.rec_name, self.share * 100)

    def _expand_tree(self, name):
        return True


class OptionSubscription:
    __name__ = 'contract.wizard.option_subscription'

    def default_options_displayer(self, values):
        res = super(OptionSubscription, self).default_options_displayer(values)
        contract = self.get_contract()
        res['is_loan'] = contract.is_loan if contract else False
        return res

    @classmethod
    def init_default_childs(cls, contract, coverage, option, parent_dict):
        res = super(OptionSubscription, cls).init_default_childs(contract,
            coverage, option, parent_dict)
        for ordered_loan in [x for x in contract.ordered_loans]:
            loan_share = None
            loan = ordered_loan.loan
            for share in option.loan_shares if option else []:
                if share.loan == loan:
                    loan_share = share
                    break
            res.append({
                    'loan': loan.id,
                    'order': ordered_loan.number,
                    'share': loan_share.share if loan_share else 1,
                    'is_selected': (loan_share is not None
                        or parent_dict['is_selected']),
                    'selection': 'manual',
                    })
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
    __name__ = 'contract.wizard.option_subscription.options_displayer'

    is_loan = fields.Boolean('Is Loan')
    default_share = fields.Numeric('Default Loan Share', digits=(16, 4),
        domain=[If(Bool(Eval('default_share')),
                [('default_share', '>', 0), ('default_share', '<=', 1)],
                [])],
        states={'invisible': ~Eval('is_loan')})

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


class WizardOption:
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

    @fields.depends('loan', 'order')
    def on_change_with_name(self, name=None):
        if self.loan:
            return '    %s %s' % (self.order, self.loan.rec_name)
        else:
            return super(WizardOption, self).on_change_with_name(name)

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

    def new_line(self, name, line=None):
        new_line = super(DisplayContractPremium, self).new_line(name, line)
        if not line or not line.loan:
            return new_line
        new_line['name'] = '[%s] %s' % (line.loan.number, new_line['name'])
        return new_line
