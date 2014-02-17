from itertools import repeat, izip, chain
from decimal import Decimal

from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.rpc import RPC

from trytond.modules.cog_utils import model, fields, coop_date
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.offered_insurance.business_rule.premium_rule import \
    PRICING_FREQUENCY


__metaclass__ = PoolMeta
__all__ = [
    'PaymentMethod',
    'Premium',
    'PremiumTaxRelation',
    'PremiumFeeRelation',
    'BillingData',
    'BillingPeriod',
    'ContractDoBilling',
    'ContractDoBillingParameters',
    'ContractDoBillingBill',
    ]


class PaymentMethod(model.CoopSQL, model.CoopView):
    'Payment Method'

    __name__ = 'billing.payment.method'

    name = fields.Char('Name')
    code = fields.Char('Code', required=True)
    payment_term = fields.Many2One('billing.payment.term', 'Payment Term',
        ondelete='RESTRICT', required=True)
    payment_mode = fields.Selection([
            ('cash', 'Cash'),
            ('check', 'Check'),
            ('wire_transfer', 'Wire Transfer'),
            ('direct_debit', 'Direct Debit'),
            ],
        'Payment Mode', required=True)
    allowed_payment_dates = fields.Char('Allowed Payment Dates',
        states={'invisible': Eval('payment_mode', '') != 'direct_debit'},
        help='A list of comma-separated numbers that resolves to the list of'
        'allowed days of the month eligible for direct debit.\n\n'
        'An empty list means that all dates are allowed')

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    def get_rule(self):
        return self.payment_term

    def get_allowed_date_values(self):
        if not self.payment_mode == 'direct_debit':
            return [('', '')]
        if not self.allowed_payment_dates:
            return [(str(x), '%02d' % x) for x in xrange(1, 32)]
        return [(str(x), '%02d' % int(x)) for x in
            self.allowed_payment_dates.split(',')]


class PremiumTaxRelation(model.CoopSQL, model.CoopView):
    'Premium Tax Relation'

    __name__ = 'contract.billing.premium-tax'

    price_line = fields.Many2One('contract.billing.premium', 'Premium',
        ondelete='CASCADE')
    tax_desc = fields.Many2One('account.tax.description', 'Tax',
        ondelete='RESTRICT')
    to_recalculate = fields.Boolean('Recalculate at billing')
    amount = fields.Numeric('Amount')

    @classmethod
    def default_to_recalculate(cls):
        return False


class PremiumFeeRelation(model.CoopSQL, model.CoopView):
    'Premium Fee Relation'

    __name__ = 'contract.billing.premium-fee'

    price_line = fields.Many2One('contract.billing.premium', 'Premium',
        ondelete='CASCADE')
    fee_desc = fields.Many2One('account.fee.description', 'Fee',
        ondelete='RESTRICT')
    to_recalculate = fields.Boolean('Recalculate at billing')
    amount = fields.Numeric('Amount')

    @classmethod
    def default_to_recalculate(cls):
        return False


class Premium(model.CoopSQL, model.CoopView, ModelCurrency):
    'Premium'

    __name__ = 'contract.billing.premium'

    amount = fields.Numeric('Amount')
    name = fields.Function(
        fields.Char('Short Description'),
        'get_short_name')
    master = fields.Many2One('contract.billing.premium', 'Master Line',
        ondelete='CASCADE')
    on_object = fields.Reference('Priced object', 'get_line_target_models')
    frequency = fields.Selection(PRICING_FREQUENCY + [('', '')], 'Frequency')
    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    all_lines = fields.One2Many('contract.billing.premium', 'master', 'Lines',
        readonly=True, loading='lazy')
    estimated_total = fields.Function(
        fields.Numeric('Estimated total'),
        'get_estimated_total')
    estimated_taxes = fields.Function(
        fields.Numeric('Estimated Taxes'),
        'get_estimated_taxes')
    estimated_fees = fields.Function(
        fields.Numeric('Estimated Fees'),
        'get_estimated_fees')
    tax_lines = fields.One2Many('contract.billing.premium-tax',
        'price_line', 'Tax Lines')
    fee_lines = fields.One2Many('contract.billing.premium-fee',
        'price_line', 'Fee Lines')

    def get_estimated_total(self, name):
        return self.amount + self.estimated_fees + self.estimated_taxes

    def get_short_name(self, name):
        if self.on_object:
            return self.on_object.get_name_for_billing()
        return 'Main Line'

    def init_values(self):
        if not hasattr(self, 'name') or not self.name:
            self.name = ''
        self.amount = 0
        self.all_lines = []

    @classmethod
    def must_create_detail(cls, detail):
        if detail.on_object:
            if detail.on_object.__name__ == 'billing.premium.rule.component':
                if detail.on_object.kind in ('tax', 'fee'):
                    return False
                return True
        return True

    def get_good_on_object(self, line):
        if not line.on_object:
            return None
        target = line.on_object
        if target.__name__ == 'billing.premium.rule.component':
            if target.kind == 'tax':
                return target.tax
            if target.kind == 'fee':
                return target.fee
            # TODO : set a valid on_object for base amount lines
            return None
        return target

    def init_from_result_line(self, line, build_details=False):
        if not line:
            return
        PremiumModel = Pool().get(self.__name__)
        self.init_values()
        self.on_object = self.get_good_on_object(line)
        self.start_date = line.start_date if hasattr(
            line, 'start_date') else None
        self.frequency = line.frequency if hasattr(line, 'frequency') else ''
        self.contract = line.contract if hasattr(line, 'contract') else None
        for detail in line.details:
            if not self.must_create_detail(detail):
                continue
            detail_line = PremiumModel()
            detail_line.init_from_result_line(detail)
            if detail_line.amount:
                self.all_lines.append(detail_line)
        if not line.details:
            self.amount = line.amount
        else:
            self.amount = sum(map(lambda x: x.amount, self.all_lines))
        if build_details:
            self.build_tax_lines(line)
            self.build_fee_lines(line)

    def get_tax_details(self, line, taxes):
        for elem in line.details:
            if (elem.on_object and elem.on_object.__name__ ==
                    'billing.premium.rule.component' and
                    elem.on_object.kind == 'tax'):
                if elem.on_object.tax.id in taxes:
                    taxes[elem.on_object.tax.id].append(elem)
                else:
                    taxes[elem.on_object.tax.id] = [elem]
            else:
                self.get_tax_details(elem, taxes)

    def build_tax_lines(self, line):
        tax_details = {}
        if not (hasattr(self, 'tax_lines') and self.tax_lines):
            self.tax_lines = []
        self.get_tax_details(line, tax_details)
        TaxDesc = Pool().get('account.tax.description')
        TaxRelation = Pool().get('contract.billing.premium-tax')
        for tax_id, tax_lines in tax_details.iteritems():
            the_tax = TaxDesc(tax_id)
            tax_relation = TaxRelation()
            tax_relation.tax_desc = the_tax
            tax_relation.to_recalculate = tax_lines[0].to_recalculate
            tax_relation.amount = sum(map(lambda x: x.amount, tax_lines))
            self.tax_lines.append(tax_relation)

    def get_fee_details(self, line, fees):
        for elem in line.details:
            if (elem.on_object and elem.on_object.__name__ ==
                    'billing.premium.rule.component' and
                    elem.on_object.kind == 'fee'):
                if elem.on_object.fee.id in fees:
                    fees[elem.on_object.fee.id].append(elem)
                else:
                    fees[elem.on_object.fee.id] = [elem]
            else:
                self.get_fee_details(elem, fees)

    def build_fee_lines(self, line):
        fee_details = {}
        if not (hasattr(self, 'fee_lines') and self.fee_lines):
            self.fee_lines = []
        self.get_fee_details(line, fee_details)
        FeeDesc = Pool().get('account.fee.description')
        FeeRelation = Pool().get('contract.billing.premium-fee')
        for fee_id, fee_lines in fee_details.iteritems():
            the_fee = FeeDesc(fee_id)
            fee_relation = FeeRelation()
            fee_relation.fee_desc = the_fee
            fee_relation.to_recalculate = fee_lines[0].to_recalculate
            fee_relation.amount = sum(map(lambda x: x.amount, fee_lines))
            self.fee_lines.append(fee_relation)

    def get_estimated_taxes(self, field_name):
        res = 0
        for elem in self.tax_lines:
            res += elem.amount
        return res

    def get_estimated_fees(self, field_name):
        res = 0
        for elem in self.fee_lines:
            res += elem.amount
        return res

    @classmethod
    def get_line_target_models(cls):
        f = lambda x: (x, x)
        res = [
            f(''),
            f('offered.product'),
            f('offered.option.description'),
            f('contract'),
            f('contract.option'),
            f('contract.covered_data'),
            f('account.tax.description'),
            f('account.fee.description'),
            f('extra_premium.kind'),
            ]
        return res

    def get_account_for_billing(self):
        return self.on_object.get_account_for_billing()

    def get_number_of_days_at_date(self, start_date, end_date):
        if self.frequency == 'one_shot':
            final_date = end_date
        else:
            final_date = coop_date.add_frequency(self.frequency, start_date)
        return coop_date.number_of_days_between(start_date, final_date) - 1

    def get_currency(self):
        if self.contract:
            return self.contract.currency
        elif self.master:
            return self.master.currency

    def get_base_amount_for_billing(self):
        return self.amount

    def calculate_bill_contribution(self, work_set, period):
        number_of_days = coop_date.number_of_days_between(*period)
        price_line_days = self.get_number_of_days_at_date(*period)
        convert_factor = number_of_days / Decimal(price_line_days)
        amount = self.get_base_amount_for_billing() * convert_factor
        amount = work_set.currency.round(amount)
        account = self.get_account_for_billing()
        work_set.contributions.append({
                'from': self.on_object,
                'start_date': period[0],
                'end_date': period[1],
                'base_amount': self.get_base_amount_for_billing(),
                'final_amount': amount,
                'ratio': convert_factor,
                })
        line = work_set.lines[(self.on_object, account)]
        line.second_origin = self.on_object
        line.credit += amount
        work_set.total_amount += amount
        line.account = account
        line.party = self.contract.subscriber
        for type_, sub_lines, sub_line in chain(
                izip(repeat('tax'), repeat(work_set.taxes),
                    self.tax_lines),
                izip(repeat('fee'), repeat(work_set.fees),
                    self.fee_lines)):
            desc = getattr(sub_line, '%s_desc' % type_)
            values = sub_lines[desc.id]
            values['object'] = desc
            values['to_recalculate'] |= sub_line.to_recalculate
            values['amount'] += sub_line.amount * convert_factor
            values['base'] += amount
            work_set.contributions.append({
                'from': desc,
                'start_date': period[0],
                'end_date': period[1],
                'base_amount': sub_line.amount,
                'final_amount': sub_line.amount * convert_factor,
                'ratio': convert_factor,
                })
        return line


class BillingData(model.CoopSQL, model.CoopView):
    'Billing Data'
    '''
        This object will manage all billing-related content on the contract.
        It will be the target of all sql requests for automated bill
        calculation, lapsing, etc...
    '''
    __name__ = 'contract.billing.data'

    contract = fields.Many2One('contract', 'Contract', ondelete='CASCADE')
    policy_owner = fields.Function(
        fields.Many2One('party.party', 'Party', states={'invisible': True}),
        'get_policy_owner_id')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    payment_method = fields.Many2One('billing.payment.method',
        'Payment Method', ondelete='RESTRICT')
    payment_mode = fields.Function(
        fields.Char('Payment Mode', states={'invisible': True}),
        'on_change_with_payment_mode')
    payment_bank_account = fields.Many2One('bank.account',
        'Payment Bank Account',
        states={'invisible': Eval('payment_mode') != 'direct_debit'},
        domain=[('owners', '=', Eval('policy_owner'))],
        depends=['policy_owner'], ondelete='RESTRICT')
    disbursment_bank_account = fields.Many2One('bank.account',
        'Disbursement Bank Account',
        states={'invisible': Eval('payment_mode') != 'direct_debit'},
        domain=[('owners', '=', Eval('policy_owner'))],
        depends=['policy_owner'], ondelete='RESTRICT')
    payment_date_selector = fields.Function(
        fields.Selection('get_allowed_payment_dates',
            'Payment Date', states={
                'invisible': Eval('payment_mode', '') != 'direct_debit'}),
        'get_payment_date_selector', 'setter_void')
    payment_date = fields.Integer('Payment Date', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(BillingData, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))
        cls.__rpc__.update({'get_allowed_payment_dates': RPC(instantiate=0)})
        cls._error_messages.update({
                'payment_bank_account_required': 'A payment bank account must '
                'be provided if the payment mode is Direct Debit',
                })

    def check_payment_bank_acount(self):
        if (not self.contract or not self.contract.status or
                self.contract.status == 'quote'):
            return
        if self.payment_mode == 'direct_debit':
            if not self.payment_bank_account:
                self.raise_user_error('payment_bank_account_required')

    @classmethod
    def validate(cls, managers):
        super(BillingData, cls).validate(managers)
        for manager in managers:
            manager.check_payment_bank_acount()

    @fields.depends('payment_date_selector')
    def on_change_payment_date_selector(self):
        if not (hasattr(self, 'payment_date_selector') and
                self.payment_date_selector):
            return {'payment_date': None}
        return {'payment_date': int(self.payment_date_selector)}

    def get_payment_date_selector(self, name):
        if not (hasattr(self, 'payment_date') and self.payment_date):
            return ''
        return str(self.payment_date)

    def init_from_contract(self, contract, start_date):
        self.start_date = start_date
        self.payment_method = contract.offered.get_default_payment_method()
        if not self.payment_method:
            return
        good_payment_date = self.payment_method.get_allowed_date_values()[0][0]
        if good_payment_date:
            self.payment_date = int(good_payment_date)
        if self.payment_method.payment_mode == 'direct_debit':
            BankAccount = Pool().get('bank.account')
            try:
                party = contract.get_policy_owner(self.start_date)
                if party:
                    self.payment_bank_account = BankAccount.search([
                            ('party', '=', party.id)])[0]
            except IndexError:
                pass

    @fields.depends('payment_method')
    def on_change_with_payment_mode(self, name=None):
        if not (hasattr(self, 'payment_method') and self.payment_method):
            return ''
        return self.payment_method.payment_mode

    def get_policy_owner_id(self, name):
        policy_owner = (self.contract.get_policy_owner(self.start_date)
            if self.contract else None)
        return policy_owner.id if policy_owner else None

    @fields.depends('payment_method')
    def get_allowed_payment_dates(self):
        if not (hasattr(self, 'payment_method') and self.payment_method):
            return [('', '')]
        return self.payment_method.get_allowed_date_values()

    @fields.depends('payment_method', 'payment_date')
    def on_change_payment_method(self):
        allowed_vals = map(lambda x: x[0], self.get_allowed_payment_dates())
        if not (hasattr(self, 'payment_date') and self.payment_date):
            return {'payment_date_selector': allowed_vals[0],
                'payment_date': int(allowed_vals[0]) if allowed_vals[0] else
                None}
        if self.payment_date in allowed_vals:
            return {}
        return {'payment_date_selector': allowed_vals[0],
            'payment_date': int(allowed_vals[0]) if allowed_vals[0] else None}

    def get_payment_date(self):
        return self.payment_date

    @classmethod
    def get_var_names_for_full_extract(cls):
        return [('payment_method', 'light'), ('payment_bank_account', 'light'),
            ('disbursment_bank_account', 'light'), 'payment_date']

    def get_publishing_values(self):
        result = super(BillingData, self).get_publishing_values()
        result['payment_frequency'] = \
            self.payment_method.payment_term.base_frequency
        result['payment_date'] = self.payment_date
        result['sync_date'] = self.payment_method.payment_term.sync_date
        return result


class BillingPeriod(model.CoopSQL, model.CoopView):
    'Billing Period'

    __name__ = 'contract.billing.period'

    contract = fields.Many2One('contract', 'Contract', required=True,
        ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    moves = fields.One2Many('account.move', 'billing_period', 'Moves',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(BillingPeriod, cls).__setup__()
        cls._error_messages.update({
                'period_overlaps': ('Billing Period "%(first)s" and '
                    '"%(second)s" overlap.'),
                })

    def get_rec_name(self, name):
        return '%s - %s' % (self.start_date, self.end_date)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('contract',), tuple(clause[1:])]

    @classmethod
    def validate(cls, periods):
        super(BillingPeriod, cls).validate(periods)
        for period in periods:
            # TODO : Temporary remove check
            # period.check_dates()
            pass

    def check_dates(self):
        cursor = Transaction().cursor
        table = self.__table__()
        request = table.select(table.id,
            where=((table.start_date <= self.start_date and table.end_date >=
                    self.start_date)
                | (table.start_date <= self.end_date and table.end_date >=
                    self.end_date)
                | (table.start_date <= self.start_date and table.end_date <=
                    self.end_date))
                & (table.contract == self.contract.id) & (table.id != self.id))
        cursor.execute(*request)
        second_id = cursor.fetchone()
        if second_id:
            second = self.__class__(second_id[0])
            self.raise_user_error('period_overlaps', {
                    'first': self.rec_name,
                    'second': second.rec_name,
                    })


class ContractDoBillingParameters(model.CoopView):
    'Contract Do Billing Parameters'

    __name__ = 'contract.do_billing.parameters'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    contract = fields.Many2One('contract', 'Contract',
        states={'invisible': True})


class ContractDoBillingBill(model.CoopView):
    'Contract Do Billing Bill'

    __name__ = 'contract.do_billing.bill'

    moves = fields.One2Many('account.move', None, 'Bill', readonly=True)


class ContractDoBilling(Wizard):
    'Contract Do Billing'

    __name__ = 'contract.do_billing'

    start_state = 'bill_parameters'
    bill_parameters = StateView(
        'contract.do_billing.parameters',
        'billing_individual.contract_do_billing_parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'bill_display', 'tryton-go-next')])
    bill_display = StateView(
        'contract.do_billing.bill',
        'billing_individual.contract_do_billing_bill_form', [
            Button('Cancel', 'cancel_bill', 'tryton-cancel'),
            Button('Accept', 'accept_bill', 'tryton-go-next')])
    cancel_bill = StateTransition()
    accept_bill = StateTransition()

    def default_bill_parameters(self, values):
        ContractModel = Pool().get(Transaction().context.get('active_model'))
        contract = ContractModel(Transaction().context.get('active_id'))
        bill_dates = contract.next_billing_period()
        return {
            'contract': contract.id,
            'start_date': bill_dates[0],
            'end_date': bill_dates[1]}

    def default_bill_display(self, values):
        if self.bill_parameters.end_date < self.bill_parameters.start_date:
            self.raise_user_error('bad_dates')
        contract = self.bill_parameters.contract
        if self.bill_parameters.start_date < contract.start_date:
            self.raise_user_error('start_date_too_old')
        move = contract.bill()
        return {'moves': [move.id]}

    def transition_cancel_bill(self):
        Move = Pool().get('account.move')
        Move.delete(self.bill_display.moves)
        return 'end'

    def transition_accept_bill(self):
        move_date = self.bill_display.moves[-1].billing_period.end_date
        ContractModel = Pool().get(Transaction().context.get('active_model'))
        contract = ContractModel(Transaction().context.get('active_id'))
        contract.next_billing_date = coop_date.add_day(move_date, 1)
        contract.save()
        move = self.bill_display.moves[-1]
        move.post([move])
        return 'end'
