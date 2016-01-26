import datetime
from collections import defaultdict
from sql.functions import CurrentTimestamp

from sql import Null, Column, Literal
from sql.conditionals import Coalesce

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model, coop_date, utils
from trytond.modules.endorsement import values_mixin, relation_mixin


__all__ = [
    'Loan',
    'LoanIncrement',
    'LoanPayment',
    'LoanShare',
    'PremiumAmount',
    'ExtraPremium',
    'ContractLoan',
    'Endorsement',
    'EndorsementContract',
    'EndorsementLoan',
    'EndorsementCoveredElementOption',
    'EndorsementLoanShare',
    'EndorsementLoanIncrement',
    'EndorsementContractLoan',
    ]


class Loan:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'loan'

    previous_frequency = fields.Function(
        fields.Char('Previous Frequency'),
        'get_previous_frequency')
    previous_release_date = fields.Function(
        fields.Date('Previous Fund Release Date'),
        'get_previous_release_date')

    @classmethod
    def default_previous_frequency(cls):
        return cls.default_payment_frequency()

    @classmethod
    def default_previous_release_date(cls):
        return cls.default_funds_release_date()

    @fields.depends('first_payment_date', 'previous_frequency',
        'previous_release_date')
    def on_change_payment_frequency(self):
        super(Loan, self).on_change_payment_frequency()
        self.previous_frequency = self.payment_frequency

    @fields.depends('first_payment_date', 'previous_frequency',
        'previous_release_date')
    def on_change_first_payment_date(self):
        super(Loan, self).on_change_first_payment_date()

    @fields.depends('first_payment_date', 'previous_frequency',
        'previous_release_date')
    def on_change_funds_release_date(self):
        super(Loan, self).on_change_funds_release_date()
        self.previous_release_date = self.funds_release_date

    @fields.depends('first_payment_date', 'funds_release_date',
        'payment_frequency', 'previous_frequency', 'previous_release_date')
    def on_change_with_first_payment_date(self):
        if self.payment_frequency == self.previous_frequency and (
                self.funds_release_date == self.previous_release_date):
            return self.first_payment_date
        return super(Loan, self).on_change_with_first_payment_date()

    def get_previous_frequency(self, name):
        return self.payment_frequency

    def get_previous_release_date(self, name):
        return self.funds_release_date


class LoanIncrement:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'loan.increment'

    calculated_amount = fields.Function(
        fields.Numeric('Calculated Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_calculated_amount')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.4 Move Payment frequency from loan to increment
        pool = Pool()
        Loan = pool.get('loan')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        super(LoanIncrement, cls).__register__(module_name)

        loan_history_h = TableHandler(cursor, Loan, module_name, history=True)
        if loan_history_h.column_exist('payment_frequency'):
            loan_hist = Loan.__table_history__()
            increment_hist = cls.__table_history__()
            to_update = cls.__table_history__()
            update_data = increment_hist.join(loan_hist, 'LEFT OUTER',
                condition=(loan_hist.id == increment_hist.loan)
                & (increment_hist.payment_frequency == Null)
                & (Coalesce(increment_hist.write_date,
                        increment_hist.create_date) == Coalesce(
                        loan_hist.write_date, loan_hist.create_date))
                ).select(Column(increment_hist, '__id').as_('inc_id'),
                Coalesce(loan_hist.payment_frequency, 'month').as_(
                    'payment_frequency'),
                order_by=Column(loan_hist, '__id').asc)
            cursor.execute(*to_update.update(
                    columns=[to_update.payment_frequency],
                    values=[update_data.payment_frequency],
                    from_=[update_data],
                    where=update_data.inc_id == Column(to_update, '__id')))
            loan_history_h.drop_column('payment_frequency')

    def get_calculated_amount(self, name):
        return self.calculate_payment_amount()

    @fields.depends('begin_balance', 'calculated_amount', 'number_of_payments',
        'deferal', 'loan', 'payment_amount', 'payment_frequency', 'rate')
    def on_change_payment_amount(self):
        if self.payment_amount is None:
            self.payment_amount = self.calculate_payment_amount()
            self.calculated_amount = self.payment_amount

    @fields.depends('calculated_amount')
    def on_change_begin_balance(self):
        old_amount = self.payment_amount
        super(LoanIncrement, self).on_change_begin_balance()
        new_amount = self.payment_amount
        if old_amount is not None and self.calculated_amount != old_amount:
            self.payment_amount = old_amount
        self.calculated_amount = new_amount

    @fields.depends('calculated_amount')
    def on_change_deferal(self):
        old_amount = self.payment_amount
        super(LoanIncrement, self).on_change_deferal()
        new_amount = self.payment_amount
        if old_amount is not None and self.calculated_amount != old_amount:
            self.payment_amount = old_amount
        self.calculated_amount = new_amount

    @fields.depends('calculated_amount')
    def on_change_number_of_payments(self):
        old_amount = self.payment_amount
        super(LoanIncrement, self).on_change_number_of_payments()
        new_amount = self.payment_amount
        if old_amount is not None and self.calculated_amount != old_amount:
            self.payment_amount = old_amount
        self.calculated_amount = new_amount

    @fields.depends('calculated_amount')
    def on_change_payment_frequency(self):
        old_amount = self.payment_amount
        super(LoanIncrement, self).on_change_payment_frequency()
        new_amount = self.payment_amount
        if old_amount is not None and self.calculated_amount != old_amount:
            self.payment_amount = old_amount
        self.calculated_amount = new_amount

    @fields.depends('calculated_amount')
    def on_change_rate(self):
        old_amount = self.payment_amount
        super(LoanIncrement, self).on_change_rate()
        new_amount = self.payment_amount
        if old_amount is not None and self.calculated_amount != old_amount:
            self.payment_amount = old_amount
        self.calculated_amount = new_amount


class LoanPayment:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'loan.payment'


class LoanShare:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'loan.share'


class PremiumAmount:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.premium.amount'


class ExtraPremium:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option.extra_premium'

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        super(ExtraPremium, cls).__register__(module_name)

        # Migration from 1.4 : Convert 'capital_per_mil' to
        # 'initial_capital_per_mil'
        extra_table = cls.__table_history__()
        cursor.execute(*extra_table.update(
                columns=[extra_table.calculation_kind],
                values=[Literal('initial_capital_per_mil')],
                where=(extra_table.calculation_kind == 'capital_per_mil')))

    @fields.depends('option')
    def on_change_with_is_loan(self, name=None):
        if self.option:
            return super(ExtraPremium, self).on_change_with_is_loan(name)
        return Transaction().context.get('is_loan', False)


class ContractLoan:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract-loan'


class Endorsement:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement'

    loan_endorsements = fields.One2Many('endorsement.loan', 'endorsement',
        'Loan Endorsement', delete_missing=True)
    loans = fields.Function(
        fields.Many2Many('loan', '', '', 'Loans'),
        'get_loans', searcher='search_loans')

    def get_loans(self, name):
        return [x.loan.id for x in self.loan_endorsements]

    @classmethod
    def search_loans(cls, name, clause):
        return [('loan_endorsements.loan',) + tuple(clause[1:])]

    def all_endorsements(self):
        result = super(Endorsement, self).all_endorsements()
        result += self.loan_endorsements
        return result

    def find_parts(self, endorsement_part):
        # Finds the effective endorsement depending on the provided
        # endorsement part
        if endorsement_part.kind in ('loan'):
            return self.loan_endorsements
        elif endorsement_part.kind in ('loan_share'):
            return self.contract_endorsements
        return super(Endorsement, self).find_parts(endorsement_part)

    def new_endorsement(self, endorsement_part):
        if endorsement_part.kind in ('loan'):
            return Pool().get('endorsement.loan')(endorsement=self)
        if endorsement_part.kind == 'loan_share':
            return Pool().get('endorsement.contract')(endorsement=self)
        return super(Endorsement, self).new_endorsement(endorsement_part)

    @classmethod
    def group_per_model(cls, endorsements):
        result = super(Endorsement, cls).group_per_model(endorsements)
        result['endorsement.loan'] = [
            loan_endorsement for endorsement in endorsements
            for loan_endorsement in endorsement.loan_endorsements]
        return result

    @classmethod
    def apply_order(cls):
        result = super(Endorsement, cls).apply_order()
        result.insert(0, 'endorsement.loan')
        return result

    @classmethod
    @model.CoopView.button
    def reset(cls, endorsements):
        pool = Pool()
        LoanEndorsement = pool.get('endorsement.loan')
        for endorsement in endorsements:
            tmp_loans = endorsement.loans
            LoanEndorsement.delete(endorsement.loan_endorsements)
            endorsement.loan_endorsements = None
            endorsement.loan_endorsements = LoanEndorsement.create(
                [{'loan': x, 'endorsement': endorsement}
                    for x in tmp_loans])
            endorsement.effective_date = None
            endorsement.save()
        super(Endorsement, cls).reset(endorsements)


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    ordered_loans = fields.One2Many('endorsement.contract.loan',
        'contract_endorsement', 'Ordered Loans', states={
            'readonly': Eval('state') == 'applied',
            },
        depends=['state', 'definition'], delete_missing=True,
        context={'definition': Eval('definition')})

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._error_messages.update({
                'msg_contract_loan_changes': 'Contract Loans Changes',
                })

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        order.insert(order.index('contract'), 'contract-loan')
        option_idx = order.index('contract.option')
        order.insert(option_idx + 1, 'loan.share')
        order.insert(order.index('contract.premium') + 1,
            'contract.premium.amount')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        for contract in instances['contract']:
            instances['contract.premium.amount'] += contract.premium_amounts
            instances['contract-loan'] += contract.ordered_loans
        for option in instances['contract.option']:
            instances['loan.share'] += option.loan_shares

    def get_endorsement_summary(self, name):
        result = super(EndorsementContract, self).get_endorsement_summary(name)
        contract_loans_summary = [x.get_diff('contract-loan',
                x.contract_loan) for x in self.ordered_loans]
        if contract_loans_summary:
            result[2] += ['contract_loan_changes_section', '%s :' %
                self.raise_user_error('msg_contract_loan_changes',
                    raise_exception=False), contract_loans_summary]
        return result

    def apply_values(self):
        values = super(EndorsementContract, self).apply_values()
        contract_loans = []
        for contract_loan in self.ordered_loans:
            contract_loans.append(contract_loan.apply_values())
        if contract_loans:
            values['ordered_loans'] = contract_loans
        return values


class EndorsementLoan(values_mixin('endorsement.loan.field'),
        model.CoopSQL, model.CoopView):
    'Endorsement Loan'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.loan'

    loan = fields.Many2One('loan', 'Loan', required=True, ondelete='CASCADE',
        states={'readonly': Eval('state') == 'applied'}, depends=['state'])
    endorsement = fields.Many2One('endorsement', 'Endorsement', required=True,
        ondelete='CASCADE', select=True)
    increments = fields.One2Many('endorsement.loan.increment',
        'loan_endorsement', 'Loan Increments', delete_missing=True)
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    endorsement_summary = fields.Function(
        fields.Text('Endorsement Summary'),
        'get_endorsement_summary')
    state = fields.Function(
        fields.Selection([
                ('draft', 'Draft'),
                ('applied', 'Applied'),
                ], 'State'),
        'get_state', searcher='search_state')
    state_string = state.translated('state')

    @classmethod
    def __setup__(cls):
        super(EndorsementLoan, cls).__setup__()
        cls._error_messages.update({
                'not_latest_applied': ('Endorsement "%s" is not the latest '
                    'applied.'),
                'only_one_endorsement_in_progress': 'There may only be one '
                'endorsement in_progress at a given time per loan',
                'msg_increment_modifications': 'Increments Modifications',
                })
        cls.values.states = {
            'readonly': Eval('state') == 'applied',
            }
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['state', 'definition']

    @staticmethod
    def default_state():
        return 'draft'

    @property
    def base_instance(self):
        if not self.loan:
            return None
        if not self.endorsement.rollback_date:
            return self.loan
        with Transaction().set_context(
                _datetime=self.endorsement.rollback_date,
                _datetime_exclude=True):
            return Pool().get('loan')(self.loan.id)

    def get_definition(self, name):
        return self.endorsement.definition.id if self.endorsement else None

    def get_endorsement_summary(self, name):
        result = ['definition_section', self.definition.name, []]
        loan_summary = self.get_diff('loan', self.base_instance)
        if loan_summary:
            result[2] += ['loan_change_section', loan_summary]

        increment_summary = [x.get_diff('loan.increment', x.increment)
            for x in self.increments]
        if increment_summary:
            result[2] += ['increment_change_section',
                '%s :' % self.raise_user_error(
                    'msg_increment_modifications', raise_exception=False),
                increment_summary]
        return result

    def get_state(self, name):
        return self.endorsement.state if self.endorsement else 'draft'

    @classmethod
    def search_state(cls, name, clause):
        return [('endorsement.state',) + tuple(clause[1:])]

    @classmethod
    def _get_restore_history_order(cls):
        return ['loan', 'loan.increment', 'loan.payment']

    def do_restore_history(self):
        pool = Pool()
        models_to_restore = self._get_restore_history_order()
        restore_dict = {x: [] for x in models_to_restore}
        restore_dict['loan'] += [self.loan, self.base_instance]
        self._prepare_restore_history(restore_dict,
            self.endorsement.rollback_date)

        for model_name in models_to_restore:
            if not restore_dict[model_name]:
                continue
            pool.get(model_name).restore_history_before(
                list(set([x.id for x in restore_dict[model_name]])),
                self.endorsement.rollback_date)

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        for loan in instances['loan']:
            instances['loan.increment'] += loan.increments
            instances['loan.payment'] += loan.payments

    @classmethod
    def draft(cls, loan_endorsements):
        for loan_endorsement in loan_endorsements:
            latest_applied, = cls.search([
                    ('loan', '=', loan_endorsement.loan.id),
                    ('state', 'not in', ['draft', 'canceled', 'declined']),
                    ], order=[('applied_on', 'DESC')], limit=1)
            if latest_applied != loan_endorsement:
                cls.raise_user_error('not_latest_applied',
                    loan_endorsement.rec_name)

            loan_endorsement.do_restore_history()
            loan_endorsement.set_applied_on(None)
            loan_endorsement.state = 'draft'
            loan_endorsement.save()

    @classmethod
    def check_in_progress_unicity(cls, loan_endorsements):
        count = Pool().get('endorsement').search_count([
                ('loans', 'in', [x.loan.id for x in loan_endorsements]),
                ('state', '=', 'in_progress')])
        if count:
            cls.raise_user_error('only_one_endorsement_in_progress')

    @classmethod
    def apply(cls, loan_endorsements):
        for loan_endorsement in loan_endorsements:
            if loan_endorsement.endorsement.rollback_date:
                loan_endorsement.set_applied_on(
                    loan_endorsement.endorsement.rollback_date)
            else:
                loan_endorsement.set_applied_on(CurrentTimestamp())
            utils.apply_dict(loan_endorsement.loan,
                loan_endorsement.apply_values())
            loan_endorsement.loan.calculate()
            loan_endorsement.loan.save()
            loan_endorsement.save()

    def apply_values(self):
        values = super(EndorsementLoan, self).apply_values()
        increments = []
        for increment in self.increments:
            increments.append(increment.apply_values())
        if increments:
            values['increments'] = increments
        return values

    def get_endorsed_record(self):
        return self.loan


class EndorsementCoveredElementOption:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.covered_element.option'

    loan_shares = fields.One2Many('endorsement.loan.share',
        'option_endorsement', 'Loan Shares', delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementCoveredElementOption, cls).__setup__()
        cls._error_messages.update({
                'mes_loan_share_modifications': 'Loan Share Modifications',
                })

    def get_diff(self, model, base_object=None):
        result = super(EndorsementCoveredElementOption, self).get_diff(
            model, base_object)
        if self.action == 'remove':
            return result
        loan_shares_summary = [x.get_diff('loan.share', x.loan_share)
            for x in self.loan_shares]
        if loan_shares_summary:
            result += ['loan_share_change_section', '%s :'
                % (self.raise_user_error('mes_loan_share_modifications',
                        raise_exception=False)), loan_shares_summary]
        return result

    @property
    def new_shares(self):
        if self.action == 'remove':
            return []
        elif self.action == 'add':
            return list(self.loan_shares)
        else:
            existing = set([x for x in self.option.loan_shares])
            for elem in self.loan_shares:
                if elem.action == 'add':
                    existing.add(elem)
                elif elem.action == 'remove':
                    existing.remove(elem.loan_share)
                else:
                    existing.remove(elem.loan_share)
                    existing.add(elem)
        return existing

    def apply_values(self):
        EndorsementLoanShare = Pool().get('endorsement.loan.share')
        values = super(EndorsementCoveredElementOption, self).apply_values()
        shares_per_loan = defaultdict(list)
        for elem in self.new_shares:
            shares_per_loan[(elem.loan, elem.option)].append(elem)
        for share_values in shares_per_loan.itervalues():
            share_values.sort(key=lambda x: x.start_date or datetime.date.min)

        loan_share_values = []
        for loan_shares in shares_per_loan.itervalues():
            for idx, loan_share in enumerate(loan_shares):
                if not isinstance(loan_share, EndorsementLoanShare):
                    continue
                loan_share_values.append(loan_share.apply_values())
                if idx != 0:
                    previous = loan_shares[idx - 1]
                    previous_end = coop_date.add_day(loan_share.start_date, -1)
                    if (isinstance(previous, EndorsementLoanShare) and
                            previous.action in ('add', 'update')):
                        loan_share_values[-2][-1]['end_date'] = previous_end
                    else:
                        if ((previous.start_date or datetime.date.min) <
                                loan_share.start_date):
                            loan_share_values.append(('write', [previous.id],
                                    {'end_date': previous_end}))
                        else:
                            loan_share_values.append(('remove', [previous.id]))
        if loan_share_values:
            if self.action == 'add':
                values[1][0]['loan_shares'] = loan_share_values
            elif self.action == 'update':
                values[2]['loan_shares'] = loan_share_values
        return values

    @classmethod
    def updated_struct(cls, option):
        struct = super(EndorsementCoveredElementOption, cls).updated_struct(
            option)
        EndorsementLoanShare = Pool().get('endorsement.loan.share')
        struct['loan_shares'] = shares = defaultdict(list)
        for share in (option.new_shares
                if isinstance(option, cls) else option.loan_shares):
            shares[share.loan].append(
                EndorsementLoanShare.updated_struct(share))
        return struct


class EndorsementLoanShare(relation_mixin(
            'endorsement.loan.share.field', 'loan_share', 'loan.share',
            'Loan Shares'),
        model.CoopSQL, model.CoopView):
    'Loan Share'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.loan.share'

    option_endorsement = fields.Many2One(
        'endorsement.contract.covered_element.option', 'Option Endorsement',
        required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    loan = fields.Function(
        fields.Many2One('loan', 'Loan'),
        '')
    share = fields.Function(
        fields.Numeric('Share', digits=(5, 4)),
        '')
    start_date = fields.Function(
        fields.Date('Start Date'),
        '')

    @classmethod
    def __setup__(cls):
        super(EndorsementLoanShare, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    @fields.depends('values')
    def on_change_with_loan(self, name=None):
        return self.values.get('loan', self.loan_share.loan.id)

    @fields.depends('values')
    def on_change_with_share(self, name=None):
        if self.loan_share:
            return self.values.get('share', self.loan_share.share)
        else:
            return self.values.get('share', None)

    @fields.depends('values')
    def on_change_with_start_date(self, name=None):
        if self.loan_share:
            return self.values.get('start_date', self.loan_share.start_date)
        else:
            return self.values.get('start_date', None)

    def get_definition(self, name):
        return self.option_endorsement.definition.id

    @property
    def option(self):
        if self.option_endorsement.option:
            return self.option_endorsement.option
        return self.option_endorsement

    @classmethod
    def updated_struct(cls, loan_share):
        return {'instance': loan_share}

    @classmethod
    def _ignore_fields_for_matching(cls):
        return {'option'}


class EndorsementLoanIncrement(relation_mixin(
            'endorsement.loan.increment.field', 'increment', 'loan.increment',
            'Loan Increments'),
        model.CoopSQL, model.CoopView):
    'Loan Increment'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.loan.increment'

    loan_endorsement = fields.Many2One('endorsement.loan', 'Loan Endorsement',
        required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')

    @classmethod
    def __setup__(cls):
        super(EndorsementLoanIncrement, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.loan_endorsement.definition.id

    @classmethod
    def _ignore_fields_for_matching(cls):
        return super(EndorsementLoanIncrement,
            cls)._ignore_fields_for_matching() | {'loan', 'number',
                'number_of_payments', 'calculated_amount', 'payment_amount',
                'end_date', 'begin_balance', 'currency', 'currency_symbol',
                'currency_digits', 'start_date'}


class EndorsementContractLoan(relation_mixin(
            'endorsement.contract.loan.field', 'contract_loan',
            'contract-loan', 'Contract Loan'),
        model.CoopSQL, model.CoopView):
    'Contract Loan'
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract.loan'

    contract_endorsement = fields.Many2One('endorsement.contract',
        'Contract Endorsement', required=True, select=True, ondelete='CASCADE')
    definition = fields.Function(
        fields.Many2One('endorsement.definition', 'Definition'),
        'get_definition')
    loan = fields.Function(
        fields.Many2One('loan', 'Loan'),
        '')

    @classmethod
    def __setup__(cls):
        super(EndorsementContractLoan, cls).__setup__()
        cls.values.domain = [('definition', '=', Eval('definition'))]
        cls.values.depends = ['definition']

    @classmethod
    def default_definition(cls):
        return Transaction().context.get('definition', None)

    def get_definition(self, name):
        return self.contract_endorsement.definition.id

    @classmethod
    def _ignore_fields_for_matching(cls):
        return super(EndorsementContractLoan,
            cls)._ignore_fields_for_matching() | {'contract'}
