import datetime
import bisect
from decimal import Decimal

from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool, If, Not
from trytond.model import Workflow
from trytond.tools import grouped_slice

from trytond.modules.cog_utils import utils, coop_date, fields, model
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'Loan',
    'LoanIncrement',
    'LoanPayment',
    ]

LOAN_KIND = [
    ('fixed_rate', 'Fixed Rate'),
    ('interest_free', 'Interest Free Loan'),
    ('graduated', 'Graduated'),
    ('intermediate', 'Intermediate'),
    ('balloon', 'Balloon'),
    ]

DEFERALS = [
    ('', ''),
    ('partially', 'Partially Deferred'),
    ('fully', 'Fully deferred'),
    ]

_STATES = {'readonly': Eval('state') != 'draft'}
_DEPENDS = ['state']
_STATES_INCREMENT = {'required': Eval('loan_state') == 'calculated'}
LOAN_FIELDS_FOR_INCREMENTS = ['kind', 'deferal', 'duration', 'duration_unit',
    'deferal_duration', 'increments', 'rate', 'payment_frequency',
    'first_payment_date', 'funds_release_date']


class Loan(Workflow, model.CoopSQL, model.CoopView):
    'Loan'

    __name__ = 'loan'
    _func_key = 'number'

    number = fields.Char('Number', required=True, readonly=True, select=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, ondelete='RESTRICT',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        )
    kind = fields.Selection(LOAN_KIND, 'Kind', required=True, sort=False,
        states=_STATES, depends=_DEPENDS)
    kind_string = kind.translated('kind')
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT', states=_STATES, depends=_DEPENDS)
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'on_change_with_currency_symbol')
    duration = fields.Function(
        fields.Integer('Duration', required=True, states=_STATES,
             depends=_DEPENDS, help='Deferal included'),
        'get_duration', 'setter_void')
    duration_unit = fields.Function(
        fields.Selection([('month', 'Month'), ('year', 'Year')], 'Unit',
            sort=False, required=True),
        'get_duration_unit', 'setter_void')
    duration_unit_string = duration_unit.translated('duration_unit')
    payment_frequency = fields.Function(
        fields.Selection([
                ('month', 'Month'),
                ('quarter', 'Quarter'),
                ('half_year', 'Half-year'),
                ('year', 'Year')],
            'Payment Frequency', sort=False, required=True,
            states=_STATES, depends=_DEPENDS),
        'get_non_deferal_increment_field', 'setter_void')
    payment_frequency_string = payment_frequency.translated(
        'payment_frequency')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES,
        depends=['currency_digits', 'kind', 'state'],
        required=True)
    funds_release_date = fields.Date('Funds Release Date', required=True,
        states=_STATES, depends=_DEPENDS)
    first_payment_date = fields.Date('First Payment Date', required=True,
        states=_STATES, depends=_DEPENDS)
    loan_shares = fields.One2Many('loan.share', 'loan', 'Loan Shares',
        readonly=True, states={'invisible': ~Eval('loan_shares')},
        delete_missing=True, target_not_indexed=True)
    insured_persons = fields.Function(
        fields.Many2Many('party.party', None, None, 'Insured Persons',
            states={'invisible': ~Eval('insured_persons')}),
        'get_insured_persons', searcher='search_insured_persons')
    insured_persons_name = fields.Function(
        fields.Char('Insured Persons'),
        'get_insured_persons_name',
        searcher='search_insured_persons_name')
    rate = fields.Numeric('Annual Rate', digits=(16, 4),
        states={
            'required': Eval('kind').in_(
                ['fixed_rate', 'intermediate', 'balloon']),
            'readonly':
                (Eval('state') != 'draft') | (Eval('kind') == 'interest_free'),
            },
        domain=[If(
                Eval('kind').in_(['fixed_rate', 'intermediate', 'balloon']),
                ['OR', ('rate', '>', 0), ('rate', '=', None)],
                [],
                )],
        depends=['kind', 'state'])
    payments = fields.One2Many('loan.payment', 'loan', 'Payments',
        # We force the order to make sure bisect will work properly
        order=[('start_date', 'ASC')],
        readonly=True, delete_missing=True)
    increments = fields.One2Many('loan.increment', 'loan', 'Increments',
        domain=['OR',
            [('start_date', '>=', Eval('first_payment_date'))],
            [('start_date', '=', None)],
            ],
        states={
            'readonly': (
                Eval('state') != 'draft'),
            },
        depends=['state', 'first_payment_date', 'kind'], delete_missing=True)
    deferal = fields.Function(
        fields.Selection(DEFERALS, 'Deferal',
            states={
                'invisible': ~Eval('kind').in_(
                    ['fixed_rate', 'interest_free']),
                'readonly': Eval('state') != 'draft',
                },
            depends=['kind', 'state']),
        'get_first_increment_field', 'setter_void')
    deferal_string = deferal.translated('deferal')
    deferal_duration = fields.Function(
        fields.Integer('Deferal Duration',
            states={
                'invisible': ~Eval('deferal') | ~Eval('kind').in_(
                    ['fixed_rate', 'interest_free']),
                'required': Bool(Eval('deferal', '')),
                'readonly': Eval('state') != 'draft'
                },
            depends=['deferal', 'kind', 'state']),
        'get_deferal_duration', 'setter_void')
    end_date = fields.Function(
        fields.Date('End Date'),
        'get_end_date')
    current_loan_shares = fields.Function(
        fields.One2Many('loan.share', None, 'Current Loan Share'),
        'get_current_loan_shares')
    order = fields.Function(
        fields.Integer('Order'),
        'get_order')
    outstanding_balance = fields.Function(
        fields.Numeric('Outstanding Balance',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_outstanding_loan_balance')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ], 'State', readonly=True)
    state_string = state.translated('state')
    contracts = fields.Many2Many('contract-loan', 'loan', 'contract',
        'Contracts')
    display_warning = fields.Function(
        fields.Boolean('Warning'),
        'on_change_with_display_warning')

    @classmethod
    def __setup__(cls):
        super(Loan, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))
        cls._error_messages.update({
                'no_sequence': 'No loan sequence defined',
                'used_on_non_project_contract': (
                    'The loan "%(loan)s" is used on '
                    'the contract(s) "%(contract)s". '
                    'Are you sure you want to continue?'),
                })
        cls._transitions |= set((
                ('draft', 'calculated'),
                ('calculated', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                'calculate_loan': {
                    'invisible': Eval('state') != 'draft',
                    },
                'add_manual_increment': {
                    'invisible': Eval('state') != 'draft',
                    },
                })

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        with Transaction().set_user(0):
            loan_sequences = Sequence.search([('code', '=', 'loan')])
        sequences_dict = dict([(x.company.id, x) for x in loan_sequences])
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('number'):
                sequence = sequences_dict.get(vals.get('company'), None)
                if not sequence:
                    cls.raise_user_error('no_sequence')
                vals['number'] = Sequence.get_id(sequence.id)
        return super(Loan, cls).create(vlist)

    @classmethod
    def view_attributes(cls):
        return [('/form/notebook/page[@id="quote_share"]', 'states',
                {'invisible': ~Eval('loan_shares')}),
            (
                '/form/notebook/page[@id="main"]/group[@id="warning"]',
                'states',
                {'invisible': Not(Eval('display_warning', False))}
            )]

    @classmethod
    def _export_skips(cls):
        return super(Loan, cls)._export_skips() | {'loan_shares', 'contracts'}

    @classmethod
    def _export_light(cls):
        return super(Loan, cls)._export_light() | {'company', 'currency'}

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['number']

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_kind():
        return 'fixed_rate'

    @staticmethod
    def default_payment_frequency():
        return 'month'

    @staticmethod
    def default_duration_unit():
        return 'month'

    @staticmethod
    def default_deferal():
        return ''

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_funds_release_date():
        return Transaction().context.get('start_date', None)

    @staticmethod
    def default_order():
        return Transaction().context.get('nb_of_loans', 0) + 1

    @staticmethod
    def calculate_rate(annual_rate, payment_frequency):
        if not annual_rate:
            annual_rate = Decimal(0)
        coeff = coop_date.convert_frequency(payment_frequency, 'year')
        return annual_rate / Decimal(coeff)

    @staticmethod
    def calculate_payment_amount(annual_rate, number_of_payments, amount,
            currency, payment_frequency, deferal=None):
        if not number_of_payments:
            return
        rate = Loan.calculate_rate(annual_rate, payment_frequency)
        if not deferal:
            if rate:
                den = Decimal((1 - (1 + rate) ** (-number_of_payments)))
                res = amount * rate / den
            else:
                res = amount / Decimal(number_of_payments)
        elif deferal == 'partially':
            res = amount * rate
        elif deferal == 'fully':
            res = Decimal(0)
        return currency.round(res)

    def init_increments(self):
        if self.kind == 'graduated' or any([getattr(x, 'manual', None)
                    for x in getattr(self, 'increments', [])]):
            # Nothing to do, we keep current increments
            return
        elif self.kind in ['intermediate', 'balloon']:
            deferal = 'partially'
            coeff = Decimal(coop_date.convert_frequency(self.duration_unit,
                    self.payment_frequency))
            deferal_duration = (self.duration / coeff - 1
                if self.duration else None)
            deferal_duration_unit = self.payment_frequency
        else:
            deferal = getattr(self, 'deferal', None)
            deferal_duration = getattr(self, 'deferal_duration', None)
            deferal_duration_unit = self.payment_frequency
        if deferal and deferal_duration:
            self.increments = self.create_increments_from_deferal(
                deferal_duration, deferal_duration_unit, deferal)
        elif self.duration:
            coeff = Decimal(coop_date.convert_frequency(self.duration_unit,
                    self.payment_frequency))
            self.increments = [self.create_increment(self.duration / coeff,
                    self.payment_frequency)]

    def update_increments_and_calculate_payments(self):
        increments = list(self.increments)

        for increment in increments:
            increment.manual = getattr(increment, 'manual', None)
            increment.start_date = getattr(increment, 'start_date', None)
            increment.number = getattr(increment, 'number', None)
            increment.deferal = getattr(increment, 'deferal', None)

        manual_increments = [x for x in increments
            if x.start_date and x.manual and not x.number]
        for manual_increment in manual_increments:
            increments = self.insert_manual_increment(manual_increment,
                increments)
        Payment = Pool().get('loan.payment')
        payments = [Payment(
                kind='releasing_funds',
                number=0,
                start_date=self.funds_release_date,
                outstanding_balance=self.amount,
                )]
        begin_balance = self.amount
        if self.first_payment_date == self.on_change_with_first_payment_date():
            # First payment date is synchronised with funds release date
            initial_date = self.funds_release_date
            shift = 1
        else:
            initial_date = self.first_payment_date
            shift = 0
        # Force duration calculation as it could be outdated when inserting
        # manual increment
        duration = self.get_duration(increments=increments)
        n = 0
        number_of_payments_in_months = 0
        from_date = self.first_payment_date
        for i, increment in enumerate(increments, 1):
            increment.number = i
            if increment.manual and increment.start_date:
                from_date = increment.start_date
            else:
                increment.start_date = from_date
            if increment.manual and increment.begin_balance:
                begin_balance = increment.begin_balance
            else:
                increment.begin_balance = begin_balance
            if increment.begin_balance and increment.payment_amount is None:
                increment.payment_amount = Loan.calculate_payment_amount(
                    increment.rate, increment.number_of_payments,
                    increment.begin_balance, self.currency,
                    increment.payment_frequency,
                    increment.deferal
                    )
            if not begin_balance:
                continue
            for j in range(1, increment.number_of_payments + 1):
                n += 1
                coeff = Decimal(coop_date.convert_frequency(
                        increment.payment_frequency, 'month'))
                number_of_payments_in_months += 1 / coeff
                payment = Payment.create_payment(from_date, n,
                    begin_balance, increment, increment.payment_frequency,
                    self.currency,
                    number_of_payments_in_months == duration)
                payments.append(payment)
                begin_balance = payment.outstanding_balance
                if not increment.start_date or not increment.manual:
                    from_date = coop_date.add_duration(initial_date,
                        increment.payment_frequency, n + shift,
                        stick_to_end_of_month=True)
                else:
                    from_date = coop_date.add_duration(increment.start_date,
                        increment.payment_frequency, j,
                        stick_to_end_of_month=True)
        self.increments = increments
        self.payments = payments

    def calculate(self):
        self.init_increments()
        self.update_increments_and_calculate_payments()
        self.state = 'calculated'

    @classmethod
    def insert_manual_increment(cls, increment, increments):
        increments_to_keep = [x for x in increments
            if x.start_date and x.start_date < increment.start_date]
        i = increments.index(increment)
        increments_added_after_manual_increments = [x for x in increments
            if not x.number and increments.index(x) > i]
        if increments_to_keep:
            prev_increment = increments_to_keep[-1]
            prev_increment.number_of_payments, is_exact = (
                coop_date.duration_between_and_is_it_exact(
                    prev_increment.start_date,
                    coop_date.add_day(increment.start_date, -1),
                    prev_increment.payment_frequency))
            if not is_exact:
                prev_increment.number_of_payments += 1
        increments_to_keep.append(increment)
        return increments_to_keep + increments_added_after_manual_increments

    def create_increment(self, duration, payment_frequency,
            payment_amount=None, deferal=None):
        Increment = Pool().get('loan.increment')
        return Increment(
            number_of_payments=duration,
            payment_frequency=payment_frequency,
            rate=self.rate,
            payment_amount=payment_amount,
            deferal=deferal,
            )

    def create_increments_from_deferal(self, duration, duration_unit, deferal):
        result = [self.create_increment(duration, duration_unit,
                deferal=deferal)]
        if deferal is None:
            return result
        coeff = Decimal(coop_date.convert_frequency(self.duration_unit,
                self.payment_frequency))
        coeff2 = Decimal(coop_date.convert_frequency(duration_unit,
                self.payment_frequency))
        result.append(self.create_increment(
                self.duration / coeff - duration / coeff2,
                self.payment_frequency))
        return result

    def get_current_loan_shares(self, name):
        contract_id = Transaction().context.get('contract', None)
        if contract_id is None:
            return []
        return [x.id for x in Pool().get('loan.share').search([
                    ('loan', '=', self.id),
                    ('contract', '=', contract_id)])]

    def get_rec_name(self, name):
        name = []
        if getattr(self, 'order', None):
            name.append(str(self.order))
        if self.number:
            name.append('[%s]' % self.number)
        if self.kind:
            name.append(coop_string.translate_value(self, 'kind'))
        if self.amount:
            name.append(self.currency.amount_as_string(self.amount))
        return ' '.join(name)

    @classmethod
    def get_order(cls, loans, name=None):
        ret = {x.id: None for x in loans}
        contract_id = Transaction().context.get('contract', None)
        if contract_id is None:
            return ret
        cursor = Transaction().cursor
        ctr_loan = Pool().get('contract-loan').__table__()
        for loan_slice in grouped_slice(loans):
            ids = [x.id for x in loan_slice]
            cursor.execute(*ctr_loan.select(
                    ctr_loan.loan, ctr_loan.number,
                    where=(ctr_loan.contract == contract_id) &
                    (ctr_loan.loan.in_(ids))))
            for loan_id, loan_number in cursor.fetchall():
                ret[loan_id] = loan_number
        return ret

    def get_end_date(self, name):
        return self.increments[-1].end_date if self.increments else None

    def get_duration(self, name=None, increments=None):
        if not increments:
            increments = self.increments
        duration = sum([x.number_of_payments / Decimal(
                    coop_date.convert_frequency(x.payment_frequency, 'month'))
                for x in increments])
        return int(round(duration))

    def get_duration_unit(self, name):
        return 'month'

    def get_first_increment_field(self, name):
        if name == 'deferal_duration':
            name = 'number_of_payments'
        if self.increments:
            return getattr(self.increments[0], name)

    def get_deferal_duration(self, name):
        return self.increments[0].number_of_payments if self.deferal else None

    def get_non_deferal_increment_field(self, name):
        increments = [x for x in self.increments if not x.deferal]
        if increments:
            return getattr(increments[0], name)

    @classmethod
    def get_insured_persons(cls, loans, name=None):
        ret = {x.id: [] for x in loans}
        pool = Pool()
        loan_share = pool.get('loan.share').__table__()
        contract_option = pool.get('contract.option').__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        cursor = Transaction().cursor
        query_table = covered_element.join(contract_option, condition=(
                contract_option.covered_element == covered_element.id)
            ).join(loan_share, condition=(
                loan_share.option == contract_option.id))
        for loan_slice in grouped_slice(loans):
            cursor.execute(
                *query_table
                .select(
                    loan_share.loan, covered_element.party,
                    where=loan_share.loan.in_([i.id for i in loan_slice]),
                    group_by=[loan_share.loan, covered_element.party],
                ))
            for loan_id, party_id in cursor.fetchall():
                ret[loan_id].append(party_id)
        return ret

    def get_payment(self, at_date=None):
        if not at_date:
            at_date = utils.today()
        bisect_list = utils.ProxyListWithGetter(self.payments,
            lambda x: x.start_date)
        insert_idx = bisect.bisect_right(bisect_list, at_date)
        return self.payments[insert_idx - 1] if insert_idx else None

    def get_outstanding_loan_balance(self, name=None, at_date=None):
        payment = self.get_payment(at_date)
        return payment.outstanding_balance if payment else None

    def init_dict_for_rule_engine(self, current_dict):
        current_dict['loan'] = self

    def get_loan_share(self, party, at_date=None):
        if not at_date:
            at_date = utils.today()
        for share in self.loan_shares:
            if (share.person == party
                    and (not share.start_date or share.start_date <= at_date)
                    and (at_date <= share.end_date)):
                return share

    def get_publishing_values(self):
        result = super(Loan, self).get_publishing_values()
        result['amount'] = self.amount
        result['start_date'] = self.funds_release_date
        result['duration'] = self.duration
        return result

    def get_payment_amount(self, at_date=None):
        at_date = at_date or utils.today()
        increment = utils.get_value_at_date(self.increments, at_date,
            'start_date')
        return increment.payment_amount if increment else 0

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        return self.currency.digits if self.currency else 2

    @fields.depends('currency')
    def on_change_with_currency_symbol(self, name=None):
        return self.currency.symbol if self.currency else ''

    @fields.depends('payment_frequency', 'funds_release_date')
    def on_change_with_first_payment_date(self):
        if self.funds_release_date and self.payment_frequency:
            return coop_date.add_duration(self.funds_release_date,
                self.payment_frequency, stick_to_end_of_month=True)
        else:
            return None

    @fields.depends('kind', 'rate')
    def on_change_with_rate(self):
        if self.kind == 'interest_free':
            return Decimal(0)
        return self.rate

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_kind(self):
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_deferal(self):
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_duration(self):
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_duration_unit(self):
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_deferal_duration(self):
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_rate(self):
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_payment_frequency(self):
        self.first_payment_date = self.on_change_with_first_payment_date()
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_first_payment_date(self):
        self.init_increments()

    @fields.depends(*LOAN_FIELDS_FOR_INCREMENTS)
    def on_change_funds_release_date(self):
        self.first_payment_date = self.on_change_with_first_payment_date()
        self.init_increments()

    @fields.depends('currency', 'currency_digits', 'currency_symbol',
        'increments', 'payment_frequency', 'state', 'rate')
    def on_change_increments(self):
        new_increments = []
        sorted_increments = sorted(self.increments,
            key=lambda x: getattr(x, 'start_date', None) or datetime.date.max)
        for idx, increment in enumerate(sorted_increments):
            new_increments.append(increment)
            is_new = False
            if not getattr(increment, 'loan_state', None):
                # We may assume a new increment
                increment.loan_state = self.state
                increment.payment_frequency = self.payment_frequency
                increment.rate = self.rate
                increment.currency = self.currency
                increment.currency_symbol = self.currency_symbol
                increment.currency_digits = self.currency_digits
                is_new = True
            if idx == 0:
                continue
            previous_end = sorted_increments[idx - 1].on_change_with_end_date()
            if not previous_end:
                continue
            previous_end = coop_date.add_duration(previous_end,
                sorted_increments[idx - 1].payment_frequency, 1)
            if is_new:
                increment.start_date = previous_end
            if increment.begin_balance or (increment.start_date and
                    increment.start_date < previous_end):
                increment.manual = True
        self.increments = new_increments

    @classmethod
    def get_insured_persons_name(cls, loans, name=None):
        ret = {}
        for loan in loans:
            line = ', '.join([x.rec_name for x in loan.insured_persons])
            ret[loan.id] = line
        return ret

    @fields.depends('insured_persons')
    def on_change_with_insured_persons_name(self, name=None):
        return ', '.join([x.rec_name for x in self.insured_persons])

    @fields.depends('payments', 'kind', 'state', 'duration')
    def on_change_with_display_warning(self, name=None):
        if self.state == 'calculated' and (not self.payments
                or not self.increments):
            return True
        elif self.state != 'calculated':
            return False
        diff = (self.payments[-1].amount or Decimal(0)) - (
            self.increments[-1].payment_amount or Decimal(0))
        if abs(diff) > Decimal(0.01) * self.duration:
            return True

    @classmethod
    def search_insured_persons(cls, name, clause):
        return [('loan_shares.person',) + tuple(clause[1:])]

    @classmethod
    def search_insured_persons_name(cls, name, clause):
        return [('insured_persons.rec_name',) + tuple(clause[1:])]

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('number',) + tuple(clause[1:])],
            [('insured_persons',) + tuple(clause[1:])],
            ]

    @classmethod
    def check_loan_is_used(cls, loans):
        for loan in loans:
            contracts = set([(x.contract.rec_name, x.contract.status_string)
                    for x in loan.loan_shares
                    if x.contract.status in ['active', 'hold']])
            if contracts:
                cls.raise_user_warning(loan.rec_name,
                    'used_on_non_project_contract', {
                        'contract': ', '.join(
                            ['%s (%s)' % (x[0], x[1]) for x in contracts]),
                        'loan': loan.rec_name,
                        })

    @classmethod
    @model.CoopView.button
    @Workflow.transition('draft')
    def draft(cls, loans):
        cls.check_loan_is_used(loans)

    @classmethod
    @model.CoopView.button
    @Workflow.transition('calculated')
    def calculate_loan(cls, loans):
        for loan in loans:
            loan.calculate()
            loan.save()

    @classmethod
    @model.CoopView.button_action('loan.act_add_manual_increment')
    def add_manual_increment(cls, loans):
        pass


class LoanIncrement(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Increment'

    __name__ = 'loan.increment'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    number = fields.Integer('Number')
    begin_balance = fields.Numeric('Begin Balance',
        states=_STATES_INCREMENT,
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits', 'loan_state'])
    start_date = fields.Date('Start Date',
        states=_STATES_INCREMENT, depends=['loan_state'])
    end_date = fields.Function(
        fields.Date('End Date', states={'invisible': ~Eval('end_date')}),
        'on_change_with_end_date')
    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE', required=True,
        select=True)
    number_of_payments = fields.Integer('Number of Payments', required=True)
    rate = fields.Numeric('Annual Rate', digits=(16, 4), required=True)
    payment_amount = fields.Numeric('Payment Amount',
        digits=(16, Eval('currency_digits', 2)),
        states=_STATES_INCREMENT, depends=['loan_state', 'currency_digits'])
    payment_frequency = fields.Selection(coop_date.DAILY_DURATION,
        'Payment Frequency', sort=False, required=True,
        domain=[('payment_frequency', 'in',
                ['month', 'quarter', 'half_year', 'year'])])
    payment_frequency_string = payment_frequency.translated(
        'payment_frequency')
    deferal = fields.Selection(DEFERALS, 'Deferal', sort=False)
    deferal_string = deferal.translated('deferal')
    manual = fields.Boolean('Manual')
    loan_state = fields.Function(
        fields.Char('Loan State'),
        'get_loan_state')

    @classmethod
    def __setup__(cls):
        super(LoanIncrement, cls).__setup__()
        cls._order.insert(0, ('number', 'ASC'))
        cls._error_messages.update({
                'invalid_number_of_payments': 'Number of payments must be > 0',
                })

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.4 Move Payment frequency from loan to increment
        pool = Pool()
        Loan = pool.get('loan')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        loan = Loan.__table__()
        loan_increment = cls.__table__()

        increment_h = TableHandler(cursor, cls, module_name)
        inexisting_start_date = not increment_h.column_exist('start_date')
        super(LoanIncrement, cls).__register__(module_name)

        loan_h = TableHandler(cursor, Loan, module_name)
        if loan_h.column_exist('payment_frequency'):
            loan_increments = []
            cursor.execute(*loan_increment.join(loan,
                    condition=loan.id == loan_increment.loan
                ).select(loan_increment.id, loan.payment_frequency))
            for loan_increment_id, payment_frequency, in cursor.fetchall():
                loan_increments.extend([
                        cls.browse([loan_increment_id]),
                        {'payment_frequency': payment_frequency}
                        ])
            if loan_increments:
                cls.write(*loan_increments)
            loan_h.drop_column('payment_frequency')

        # Migration from 1.4 Store start_date
        if inexisting_start_date:
            for increment_slice in grouped_slice(cls.search([])):
                increments = []
                for increment in increment_slice:
                    increment.start_date = increment.get_start_date(None)
                    increments.append(increment)
                cls.save(increments)

    def pre_validate(self):
        if self.number_of_payments <= 0:
            # We need to raise an error, because the domain validation record
            # domain=[('number_of_payments', '>', 0)]
            # forces the focus on the field in form view
            self.raise_user_error('invalid_number_of_payments')

    @fields.depends('begin_balance', 'currency', 'number_of_payments',
        'deferal', 'loan', 'payment_amount', 'payment_frequency', 'rate')
    def on_change_begin_balance(self):
        self.payment_amount = self.calculate_payment_amount()

    @fields.depends('begin_balance', 'currency', 'number_of_payments',
        'deferal', 'loan', 'payment_amount', 'payment_frequency', 'rate')
    def on_change_deferal(self):
        self.payment_amount = self.calculate_payment_amount()

    @fields.depends('begin_balance', 'currency', 'number_of_payments',
        'deferal', 'loan', 'payment_amount', 'payment_frequency', 'rate')
    def on_change_number_of_payments(self):
        self.payment_amount = self.calculate_payment_amount()

    @fields.depends('begin_balance', 'currency', 'number_of_payments',
        'deferal', 'loan', 'payment_amount', 'payment_frequency', 'rate')
    def on_change_payment_frequency(self):
        self.payment_amount = self.calculate_payment_amount()

    @fields.depends('begin_balance', 'currency', 'number_of_payments',
        'deferal', 'loan', 'payment_amount', 'payment_frequency', 'rate')
    def on_change_rate(self):
        self.payment_amount = self.calculate_payment_amount()

    @fields.depends('number_of_payments', 'payment_frequency', 'start_date')
    def on_change_with_end_date(self, name=None):
        if (self.start_date and self.payment_frequency
                and self.number_of_payments):
            return coop_date.add_duration(self.start_date,
                self.payment_frequency, self.number_of_payments - 1,
                stick_to_end_of_month=True)

    def calculate_payment_amount(self):
        if (self.begin_balance and self.rate and self.number_of_payments
                and self.payment_frequency):
            return self.loan.calculate_payment_amount(self.rate,
                self.number_of_payments, self.begin_balance,
                self.currency or self.loan.currency, self.payment_frequency,
                self.deferal)
        return None

    def get_func_key(self, name):
        return '|'.join([self.loan.number, str(self.number)])

    @classmethod
    def search_func_key(cls, name, clause):
        assert clause[1] == '='
        if '|' in clause[2]:
            operands = clause[2].split('|')
            if len(operands) == 2:
                loan_number, increment_number = operands
                return [
                    ('loan.number', '=', loan_number),
                    ('number', '=', int(increment_number)),
                    ]
            else:
                return [('id', '=', None)]
        else:
            return ['OR',
                [('loan.number',) + tuple(clause[1:])],
                [('number', clause[1], str(clause[2]))],
                ]

    def get_currency(self):
        return self.loan.currency

    @staticmethod
    def default_number_of_payments():
        return 0

    def get_start_date(self, name):
        start_date = self.loan.first_payment_date
        for increment in self.loan.increments:
            if increment == self:
                return start_date
            start_date = coop_date.add_duration(start_date,
                self.payment_frequency, increment.number_of_payments,
                stick_to_end_of_month=True)

    def get_loan_state(self, name):
        return self.loan.state if self.loan else None


class LoanPayment(model.CoopSQL, model.CoopView, ModelCurrency):
    'Loan Payment'

    __name__ = 'loan.payment'
    _func_key = 'number'

    loan = fields.Many2One('loan', 'Loan', ondelete='CASCADE', select=True,
        required=True)
    kind = fields.Selection([
            ('releasing_funds', 'Releasing Funds'),
            ('scheduled', 'Scheduled'),
            ('early', 'Early'),
            ('deffered', 'Deffered')], 'Kind')
    kind_string = kind.translated('kind')
    number = fields.Integer('Number')
    start_date = fields.Date('Date')
    begin_balance = fields.Function(
        fields.Numeric('Begin Balance',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_begin_balance')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    principal = fields.Numeric('Principal',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    interest = fields.Numeric('Interest',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    outstanding_balance = fields.Numeric('Outstanding Balance',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])

    @classmethod
    def __setup__(cls):
        super(LoanPayment, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))

    @staticmethod
    def default_kind():
        return 'scheduled'

    def get_currency(self):
        return self.loan.currency

    @classmethod
    def create_payment(cls, at_date, number, begin_balance, increment,
            payment_frequency, currency, is_last_payment):
        Payment = Pool().get('loan.payment')
        rate = Loan.calculate_rate(increment.rate, payment_frequency)
        payment = Payment(
            kind='scheduled',
            amount=increment.payment_amount,
            number=number,
            start_date=at_date,
            begin_balance=begin_balance,
            interest=(currency.round(begin_balance * rate) if rate else None),
            )
        interest = payment.interest or Decimal(0)
        if getattr(increment, 'deferal', None):
            if increment.deferal == 'partially':
                payment.principal = Decimal(0)
                payment.interest = payment.amount
            elif increment.deferal == 'fully':
                payment.principal = (-interest)
        else:
            if payment.begin_balance > payment.amount and not is_last_payment:
                payment.principal = payment.amount
                payment.principal -= interest
            else:
                payment.principal = payment.begin_balance
                payment.amount = payment.principal
                payment.amount += interest
        payment.outstanding_balance = payment.begin_balance - payment.principal
        return payment

    def get_begin_balance(self, name=None):
        if self.outstanding_balance is not None and self.principal is not None:
            return self.outstanding_balance + self.principal
