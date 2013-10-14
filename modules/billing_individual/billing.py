import copy
import datetime
from collections import defaultdict
from itertools import repeat, izip, chain
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, If, Date
from trytond.rpc import RPC

from trytond.modules.coop_utils import model, fields, utils, coop_date
from trytond.modules.coop_utils import export, coop_string
from trytond.modules.insurance_product.business_rule.pricing_rule import \
    PRICING_FREQUENCY
from trytond.modules.insurance_contract.contract import IS_PARTY

from payment_rule import PAYMENT_DELAYS

__all__ = [
    'PaymentMethod',
    'PriceLine',
    'PriceLineTaxRelation',
    'PriceLineFeeRelation',
    'BillingManager',
    'BillingPeriod',
    'BillingProcess',
    'BillParameters',
    'BillDisplay',
    'ProductPaymentMethodRelation',
    'Product',
    'Coverage',
    'Contract',
    'Option',
    'CoveredElement',
    'CoveredData',
    'TaxDesc',
    'FeeDesc',
    'Sequence',
    'FiscalYear',
    'Period',
    'Company',
]

PAYMENT_MODES = [
    ('cash', 'Cash'),
    ('check', 'Check'),
    ('wire_transfer', 'Wire Transfer'),
    ('direct_debit', 'Direct Debit'),
]


class PaymentMethod(model.CoopSQL, model.CoopView):
    'Payment Method'

    __name__ = 'billing.payment_method'

    name = fields.Char('Name')
    code = fields.Char('Code', required=True, on_change_with=['code', 'name'])
    payment_rule = fields.Many2One('billing.payment_rule', 'Payment Rule',
        ondelete='RESTRICT', required=True)
    payment_mode = fields.Selection(PAYMENT_MODES, 'Payment Mode',
        required=True)
    allowed_payment_dates = fields.Char('Allowed Payment Dates',
        states={'invisible': Eval('payment_mode', '') != 'direct_debit'},
        help='A list of comma-separated numbers that resolves to the list of'
        'allowed days of the month eligible for direct debit.\n\n'
        'An empty list means that all dates are allowed')

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

    def get_rule(self):
        return self.payment_rule

    def get_allowed_date_values(self):
        if not self.payment_mode == 'direct_debit':
            return [('', '')]
        if not self.allowed_payment_dates:
            return [(str(x), '%02d' % x) for x in xrange(1, 32)]
        return [(str(x), '%02d' % int(x)) for x in
            self.allowed_payment_dates.split(',')]


class PriceLineTaxRelation(model.CoopSQL, model.CoopView):
    'Price Line Tax Relation'

    __name__ = 'billing.price_line-tax-relation'

    price_line = fields.Many2One('billing.price_line', 'Price Line',
        ondelete='CASCADE')
    tax_desc = fields.Many2One('coop_account.tax_desc', 'Tax',
        ondelete='RESTRICT')
    to_recalculate = fields.Boolean('Recalculate at billing')
    amount = fields.Numeric('Amount')

    @classmethod
    def default_to_recalculate(cls):
        return False


class PriceLineFeeRelation(model.CoopSQL, model.CoopView):
    'Price Line Fee Relation'

    __name__ = 'billing.price_line-fee-relation'

    price_line = fields.Many2One('billing.price_line', 'Price Line',
        ondelete='CASCADE')
    fee_desc = fields.Many2One('coop_account.fee_desc', 'Fee',
        ondelete='RESTRICT')
    to_recalculate = fields.Boolean('Recalculate at billing')
    amount = fields.Numeric('Amount')

    @classmethod
    def default_to_recalculate(cls):
        return False


class PriceLine(model.CoopSQL, model.CoopView):
    'Price Line'

    __name__ = 'billing.price_line'

    amount = fields.Numeric('Amount')
    name = fields.Function(fields.Char('Short Description'), 'get_short_name')
    master = fields.Many2One('billing.price_line', 'Master Line')
    on_object = fields.Reference('Priced object', 'get_line_target_models')
    frequency = fields.Selection(PRICING_FREQUENCY + [('', '')], 'Frequency')
    contract = fields.Many2One('contract.contract', 'Contract')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    all_lines = fields.One2Many('billing.price_line', 'master', 'Lines',
        readonly=True, loading='lazy')
    estimated_total = fields.Function(
        fields.Numeric('Estimated total'),
        'get_estimated_total')
    estimated_taxes = fields.Function(
        fields.Numeric('Estimated Taxes'), 'get_estimated_taxes')
    estimated_fees = fields.Function(
        fields.Numeric('Estimated Fees'), 'get_estimated_fees')
    tax_lines = fields.One2Many('billing.price_line-tax-relation',
        'price_line', 'Tax Lines')
    fee_lines = fields.One2Many('billing.price_line-fee-relation',
        'price_line', 'Fee Lines')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'),
        'get_currency_symbol')

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
            if detail.on_object.__name__ == 'ins_product.pricing_component':
                if detail.on_object.kind in ('tax', 'fee'):
                    return False
                return True
        return True

    def get_good_on_object(self, line):
        if not line.on_object:
            return None
        target = line.on_object
        if target.__name__ == 'ins_product.pricing_component':
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
        PriceLineModel = Pool().get(self.__name__)
        self.init_values()
        self.on_object = self.get_good_on_object(line)
        self.start_date = line.start_date if hasattr(
            line, 'start_date') else None
        self.frequency = line.frequency if hasattr(line, 'frequency') else ''
        self.contract = line.contract if hasattr(line, 'contract') else None
        for detail in line.details:
            if not self.must_create_detail(detail):
                continue
            detail_line = PriceLineModel()
            detail_line.init_from_result_line(detail)
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
                    'ins_product.pricing_component' and
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
        TaxDesc = Pool().get('coop_account.tax_desc')
        TaxRelation = Pool().get('billing.price_line-tax-relation')
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
                    'ins_product.pricing_component' and
                    elem.on_object.kind == 'fee'):
                if elem.on_object.fee.id in fees:
                    fees[elem.on_object.fee.id].append(elem)
                else:
                    fees[elem.on_object.fee.id] = [elem]
            else:
                for detail in elem.details:
                    self.get_fee_details(detail, fees)

    def build_fee_lines(self, line):
        fee_details = {}
        if not (hasattr(self, 'fee_lines') and self.fee_lines):
            self.fee_lines = []
        self.get_fee_details(line, fee_details)
        FeeDesc = Pool().get('coop_account.fee_desc')
        FeeRelation = Pool().get('billing.price_line-fee-relation')
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
            f('offered.coverage'),
            f('contract.contract'),
            f('contract.subscribed_option'),
            f('ins_contract.covered_data'),
            f('coop_account.tax_desc'),
            f('coop_account.fee_desc')]
        return res

    def get_account_for_billing(self):
        return self.on_object.get_account_for_billing()

    def get_number_of_days_at_date(self, at_date):
        final_date = coop_date.add_frequency(self.frequency, at_date)
        return coop_date.number_of_days_between(at_date, final_date) - 1

    def get_currency(self):
        if self.contract:
            return self.contract.currency
        elif self.master:
            return self.master.currency

    def get_base_amount_for_billing(self):
        return self.amount

    def calculate_bill_contribution(self, work_set, period):
        number_of_days = coop_date.number_of_days_between(*period)
        price_line_days = self.get_number_of_days_at_date(period[0])
        convert_factor = number_of_days / Decimal(price_line_days)
        amount = self.get_base_amount_for_billing() * convert_factor
        amount = work_set['currency'].round(amount)
        account = self.get_account_for_billing()
        line = work_set['lines'][(self.on_object, account)]
        line.second_origin = self.on_object
        line.credit += amount
        work_set['total_amount'] += amount
        line.account = account
        line.party = self.contract.subscriber
        for type_, sub_lines, sub_line in chain(
                izip(repeat('tax'), repeat(work_set['taxes']),
                    self.tax_lines),
                izip(repeat('fee'), repeat(work_set['fees']),
                    self.fee_lines)):
            desc = getattr(sub_line, '%s_desc' % type_)
            values = sub_lines[desc.id]
            values['object'] = desc
            values['to_recalculate'] |= sub_line.to_recalculate
            values['amount'] += sub_line.amount * convert_factor
            values['base'] += amount
        return line


class BillingManager(model.CoopSQL, model.CoopView):
    'Billing Manager'
    '''
        This object will manage all billing-related content on the contract.
        It will be the target of all sql requests for automated bill
        calculation, lapsing, etc...
    '''
    __name__ = 'billing.billing_manager'

    contract = fields.Many2One('contract.contract', 'Contract',
        ondelete='CASCADE')
    policy_owner = fields.Function(
        fields.Many2One('party.party', 'Party', states={'invisible': True}),
        'get_policy_owner_id')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    payment_method = fields.Many2One('billing.payment_method',
        'Payment Method', on_change=['payment_method', 'payment_date'])
    payment_mode = fields.Function(
        fields.Char('Payment Mode', states={'invisible': True},
            on_change_with=['payment_method']),
        'on_change_with_payment_mode')
    payment_bank_account = fields.Many2One('bank.account',
        'Payment Bank Account',
        states={'invisible': Eval('payment_mode') != 'direct_debit'},
        domain=[('owners', '=', Eval('policy_owner'))],
        depends=['policy_owner'])
    disbursment_bank_account = fields.Many2One('bank.account',
        'Disbursement Bank Account',
        states={'invisible': Eval('payment_mode') != 'direct_debit'},
        domain=[('owners', '=', Eval('policy_owner'))],
        depends=['policy_owner'])
    payment_date_selector = fields.Function(
        fields.Selection('get_allowed_payment_dates',
            'Payment Date', selection_change_with=['payment_method'],
            states={'invisible': Eval('payment_mode', '') != 'direct_debit'},
            on_change=['payment_date_selector']),
        'get_payment_date_selector', 'setter_void')
    payment_date = fields.Integer('Payment Date', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(BillingManager, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))
        cls.__rpc__.update({'get_allowed_payment_dates': RPC(instantiate=0)})
        cls._error_messages.update({
            'payment_bank_account_required': 'A payment bank account must be '
                'provided if the payment mode is Direct Debit',
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
        for manager in managers:
            manager.check_payment_bank_acount()
        return True

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

    def on_change_with_payment_mode(self, name=None):
        if not (hasattr(self, 'payment_method') and self.payment_method):
            return ''
        return self.payment_method.payment_mode

    def get_policy_owner_id(self, name):
        policy_owner = (self.contract.get_policy_owner(self.start_date)
            if self.contract else None)
        return policy_owner.id if policy_owner else None

    def get_allowed_payment_dates(self):
        if not (hasattr(self, 'payment_method') and self.payment_method):
            return [('', '')]
        return self.payment_method.get_allowed_date_values()

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


class BillingPeriod(model.CoopSQL, model.CoopView):
    'Billing Period'
    __name__ = 'billing.period'
    contract = fields.Many2One('contract.contract', 'Contract', required=True,
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
        for period in periods:
            period.check_dates()

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


class BillParameters(model.CoopView):
    'Bill Parameters'

    __name__ = 'billing.billing_process.bill_parameters'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    contract = fields.Many2One(
        'contract.contract', 'Contract', states={'invisible': True})


class BillDisplay(model.CoopView):
    'Bill Displayer'

    __name__ = 'billing.billing_process.bill_display'

    moves = fields.One2Many('account.move', None, 'Bill', readonly=True)


class BillingProcess(Wizard):
    'Billing Process'

    __name__ = 'billing.billing_process'

    start_state = 'bill_parameters'
    bill_parameters = StateView(
        'billing.billing_process.bill_parameters',
        'billing_individual.bill_parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'bill_display', 'tryton-go-next')])
    bill_display = StateView(
        'billing.billing_process.bill_display',
        'billing_individual.bill_display_form', [
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


class ProductPaymentMethodRelation(model.CoopSQL, model.CoopView):
    'Product to Payment Method Relation definition'

    __name__ = 'billing.product-payment_method-relation'

    product = fields.Many2One('offered.product', 'Product',
        ondelete='CASCADE')
    payment_method = fields.Many2One('billing.payment_method',
        'Payment Method', ondelete='RESTRICT')
    order = fields.Integer('Order', required=True)

    @classmethod
    def get_var_names_for_full_extract(cls):
        return ['order', 'payment_method']


class Product():
    'Product'

    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    payment_delay = fields.Selection(PAYMENT_DELAYS, 'Payment delay')
    payment_methods = fields.One2Many(
        'billing.product-payment_method-relation', 'product',
        'Payment Methods', order=[('order', 'ASC')],
        domain=[('payment_method.payment_rule.payment_mode', '=',
                Eval('payment_delay', ''))],
        depends=['payment_delay'])
    account_for_billing = fields.Many2One('account.account',
        'Account for billing', required=True, depends=['company'],
        domain=[('kind', '=', 'revenue'), ('company', '=', Eval('company'))])

    def get_default_payment_method(self):
        if not self.payment_methods:
            return None
        return self.payment_methods[0].payment_method

    def get_allowed_payment_methods(self):
        result = []
        for elem in self.payment_methods:
            result.append(elem.payment_method)
        return result

    def get_account_for_billing(self):
        return self.account_for_billing

    @classmethod
    def default_payment_delay(cls):
        return 'in_advance'

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Product, cls).get_var_names_for_full_extract()
        res.extend(['payment_methods'])
        return res


class Coverage():
    'Coverage'

    __metaclass__ = PoolMeta
    __name__ = 'offered.coverage'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('kind', '=', 'revenue'), ('company', '=', Eval('company'))],
        states={
            'required': ~Eval('is_package'),
            'invisible': ~~Eval('is_package'),
            })

    def get_account_for_billing(self):
        return self.account_for_billing


class Contract():
    'Contract'

    __metaclass__ = PoolMeta
    __name__ = 'contract.contract'

    billing_managers = fields.One2Many('billing.billing_manager', 'contract',
        'Billing Managers')
    use_prices = fields.Function(
        fields.Boolean('Use Prices', states={'invisible': True}),
        'get_use_prices')
    next_billing_date = fields.Date('Next Billing Date',
        states={'invisible': ~Eval('use_prices')})
    prices = fields.One2Many(
        'billing.price_line', 'contract', 'Prices',
        states={'invisible': ~Eval('use_prices')},
        order=[('start_date', 'ASC'), ('on_object', 'ASC')])
    billing_periods = fields.One2Many('billing.period', 'contract',
        'Billing Periods')
    receivable_lines = fields.Function(
        fields.One2Many('account.move.line', None, 'Receivable Lines',
            depends=['display_all_lines', 'id'],
            domain=[('account.kind', '=', 'receivable'),
                ('reconciliation', '=', None),
                ('origin', '=', ('contract.contract', Eval('id', 0))),
                If(~Eval('display_all_lines'),
                    ('maturity_date', '<=',
                        Eval('context', {}).get(
                            'client_defined_date', Date())),
                    ())],
            on_change_with=['display_all_lines', 'id'], loading='lazy'),
        'on_change_with_receivable_lines')
    receivable_today = fields.Function(fields.Numeric('Receivable Today'),
            'get_receivable_today', searcher='search_receivable_today')
    last_bill = fields.Function(
        fields.One2Many('account.move', None, 'Last Bill'),
        'get_last_bill')
    display_all_lines = fields.Function(
        fields.Boolean('Display all lines'),
        'get_display_all_lines', 'setter_void')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_prices': {'invisible': ~Eval('use_prices')},
                })

    def on_change_with_receivable_lines(self, name=None):
        return map(lambda x: x.id, utils.get_domain_instances(self,
            'receivable_lines'))

    def get_display_all_lines(self, name):
        return False

    def get_name_for_billing(self):
        return self.offered.name + ' - Base Price'

    def new_billing_manager(self):
        return utils.instanciate_relation(self, 'billing_managers')

    def init_from_offered(self, offered, start_date=None, end_date=None):
        res = super(Contract, self).init_from_offered(offered, start_date,
            end_date)
        self.init_billing_manager()
        return res

    def init_billing_manager(self):
        if utils.is_none(self, 'billing_managers'):
            bm = self.new_billing_manager()
            bm.init_from_contract(self, self.start_date)
            self.billing_managers = [bm]
            bm.save()
        if utils.is_none(self, 'next_billing_date'):
            self.next_billing_date = self.start_date

    def get_billing_manager(self, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        for manager in self.billing_managers:
            if (manager.start_date <= date
                    and (manager.end_date is None
                        or manager.end_date >= date)):
                return manager

    def get_billing_period_at_date(self, date):
        Period = Pool().get('billing.period')
        candidates = Period.search([
                ('contract', '=', self.id), ('start_date', '<=', date),
                ('end_date', '>=', date)])
        if not candidates:
            return None
        elif len(candidates) > 1:
            raise Exception('Multiple billing periods found for date %s' %
                date)
        return (candidates[0].start_date, candidates[0].end_date)

    def next_billing_period(self):
        start_date = self.next_billing_date
        last_date = coop_date.add_day(self.start_date, -1)
        if not utils.is_none(self, 'billing_periods'):
            for period in self.billing_periods:
                if (start_date >= period.start_date and (
                        not period.end_date or period.end_date >= start_date)):
                    return (period.start_date, period.end_date)
            if period.end_date > last_date:
                last_date = period.end_date
        new_period_start = coop_date.add_day(last_date, 1)
        new_period_end = coop_date.add_frequency(
            self.get_product_frequency(last_date), last_date)
        if self.next_renewal_date:
            new_period_end = min(new_period_end, coop_date.add_day(
                self.next_renewal_date, -1))
        if self.end_date and new_period_end > self.end_date:
            return (new_period_start, self.end_date)
        return (new_period_start, new_period_end)

    @classmethod
    def get_price_line_model(cls):
        return cls._fields['prices'].model_name

    def get_product_frequency(self, at_date):
        res, errs = self.offered.get_result(
            'frequency', {
                'date': at_date,
                'appliable_conditions_date': self.appliable_conditions_date})
        if not errs:
            return res

    def store_prices(self, prices):
        if not prices:
            return
        PriceLine = Pool().get(self.get_price_line_model())
        dates = list(set([elem.start_date for elem in prices]))
        dates.sort()
        result_prices = []
        to_delete = []
        oldest = []
        if hasattr(self, 'prices') and self.prices:
            result_prices = list(filter(lambda x: x.start_date < dates[0],
                self.prices))
            to_delete = list(filter(lambda x: x.start_date >= dates[0],
                self.prices))
            by_dates = {}
            max_date = None
            for elem in result_prices:
                by_dates.setdefault(elem.start_date, []).append(elem)
                max_date = max_date if (
                    max_date and max_date > elem.start_date) \
                    else elem.start_date
            oldest = by_dates[max_date] if max_date else []
        for price in prices:
            price_line = PriceLine()
            price_line.init_from_result_line(price, True)
            try:
                price_line.end_date = dates[dates.index(price_line.start_date)
                    + 1] + datetime.timedelta(days=-1)
            except IndexError:
                pass
            result_prices.append(price_line)
        for elem in oldest:
            elem.end_date = coop_date.add_day(dates[0], -1)
            elem.save()
        if to_delete:
            PriceLine.delete(to_delete)
        self.prices = result_prices
        self.save()

    @classmethod
    @model.CoopView.button
    def button_calculate_prices(cls, contracts):
        for contract in contracts:
            contract.calculate_prices()

    def calculate_prices(self):
        prices, errs = self.calculate_prices_between_dates()
        if errs:
            return False, errs
        self.store_prices(prices)
        return True, ()

    def create_price_list(self, start_date, end_date):
        res = []
        for price_line in self.prices:
            if start_date > price_line.start_date:
                start = start_date
            else:
                start = price_line.start_date
            if not price_line.end_date:
                end = end_date
            elif end_date < price_line.end_date:
                end = end_date
            else:
                end = price_line.end_date
            if start <= end and price_line.amount:
                res.append(((start, end), price_line))
        return res

    @staticmethod
    def get_journal():
        Journal = Pool().get('account.journal')
        journal, = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        return journal

    def get_or_create_billing_period(self, period):
        BillingPeriod = Pool().get('billing.period')
        for billing_period in self.billing_periods \
                if hasattr(self, 'billing_periods') else []:
            if (billing_period.start_date, billing_period.end_date) == period:
                break
        else:
            billing_period = BillingPeriod(contract=self)
            billing_period.start_date, billing_period.end_date = period
            billing_period.save()
        return billing_period

    def init_billing_work_set(self):
        Line = Pool().get('account.move.line')
        return {
            'lines': defaultdict(lambda: Line(credit=0, debit=0)),
            'total_amount': 0,
            'taxes': defaultdict(
                lambda: {'amount': 0, 'base': 0, 'to_recalculate': False}),
            'fees': defaultdict(
                lambda: {'amount': 0, 'base': 0, 'to_recalculate': False}),
            }

    def create_billing_move(self, work_set):
        Move = Pool().get('account.move')
        Period = Pool().get('account.period')

        period_id = Period.find(self.company.id, date=work_set['period'][0])
        move = Move(
            journal=self.get_journal(),
            period=period_id,
            date=work_set['period'][0],
            origin=utils.convert_to_reference(self),
            billing_period=work_set['billing_period'],
            )
        return move

    def calculate_base_lines(self, work_set):
        for period, price_line in work_set['price_lines']:
            price_line.calculate_bill_contribution(work_set, period)

    def calculate_final_taxes_and_fees(self, work_set):
        for type_, data in chain(
                izip(repeat('tax'), work_set['taxes'].itervalues()),
                izip(repeat('fee'), work_set['fees'].itervalues())):
            account = data['object'].get_account_for_billing()
            line = work_set['lines'][(data['object'], account)]
            line.party = self.subscriber
            line.account = account
            if data['to_recalculate']:
                good_version = data['object'].get_version_at_date(
                    work_set['period'][0])
                amount = getattr(good_version,
                    'apply_%s' % type_)(data['base'])
            else:
                amount = data['amount']
            line.second_origin = data['object']
            line.credit = work_set['currency'].round(amount)
            work_set['total_amount'] += amount

    def calculate_billing_fees(self, work_set):
        if not work_set['payment_rule']:
            return
        for fee_desc in work_set['payment_rule'].appliable_fees:
            fee_line = work_set['fees'][fee_desc.id]
            fee_line['object'] = fee_desc
            fee_line['to_recalculate'] = True
            fee_line['amount'] = 0
            fee_line['base'] = work_set['total_amount']

    def compensate_existing_moves_on_period(self, work_set):
        if not work_set['billing_period'].moves:
            return
        Move = Pool().get('account.move')
        for old_move in work_set['billing_period'].moves:
            if old_move.state == 'draft':
                continue
            for old_line in old_move.lines:
                if old_line.account == self.subscriber.account_receivable:
                    continue
                line = work_set['lines'][
                    (old_line.second_origin, old_line.account)]
                line.second_origin = old_line.second_origin
                line.account = old_line.account
                if old_line.credit:
                    line.credit -= old_line.credit
                    work_set['total_amount'] -= old_line.credit
                else:
                    line.credit += old_line.debit
                    work_set['total_amount'] += old_line.debit
        Move.delete([
                x for x in work_set['billing_period'].moves
                if x.state == 'draft'])

    def apply_payment_rule(self, work_set):
        Line = Pool().get('account.move.line')
        Date = Pool().get('ir.date')
        for line in work_set['lines'].itervalues():
            if line.credit < 0:
                line.credit, line.debit = 0, -line.credit

        if work_set['total_amount'] >= 0 and work_set['payment_rule']:
            term_lines = work_set['payment_rule'].compute(
                work_set['period'][0], work_set['period'][1],
                work_set['total_amount'], work_set['currency'],
                work_set['payment_date'])
        else:
            term_lines = [(Date.today(), work_set['currency'].round(
                        work_set['total_amount']))]
        counterparts = []
        for term_date, amount in term_lines:
            counterpart = Line()
            if amount >= 0:
                counterpart.credit = 0
                counterpart.debit = amount
            else:
                counterpart.credit = - amount
                counterpart.debit = 0
            counterpart.account = self.subscriber.account_receivable
            counterpart.party = self.subscriber
            counterpart.maturity_date = term_date
            counterparts.append(counterpart)
        work_set['counterparts'] = counterparts

    def bill(self, *period):
        # Performs billing operations on the contract. It is possible to force
        # the period to work on

        # Get the period if it is not provided
        if not period:
            period = self.next_billing_period()
        if not period:
            return

        # Get the billing_manager and the billing period
        self.init_billing_manager()
        billing_manager = self.get_billing_manager(period[0])
        assert billing_manager, 'Missing Billing Manager'
        billing_period = self.get_or_create_billing_period(period)

        # Get the appliable prices ont the period. This is a list of tuples
        # of the form ((start_date, end_date), PriceLine)
        price_lines = self.create_price_list(*period)

        # Init the work_set which will be used
        currency = self.get_currency()
        work_set = self.init_billing_work_set()
        work_set['price_lines'] = price_lines
        work_set['payment_date'] = billing_manager.get_payment_date()
        work_set['payment_method'] = billing_manager.payment_method
        if work_set['payment_method']:
            work_set['payment_rule'] = work_set['payment_method'].get_rule()
        else:
            work_set['payment_rule'] = None
        work_set['period'] = period
        work_set['currency'] = currency
        work_set['billing_period'] = billing_period
        work_set['move'] = self.create_billing_move(work_set)

        # Build the basic lines which represents the total amount due on the
        # period. Those lines include product / coverage rates, taxes and fees
        self.calculate_base_lines(work_set)

        # Add billing fees if needed
        self.calculate_billing_fees(work_set)

        # Calculate final value of taxes and fees. The later the better to
        # avoid rounding problems. Some may have been already calculated in the
        # prices lines for complexity reasons
        self.calculate_final_taxes_and_fees(work_set)

        # Compensate for previous moves on the period. The current lines
        # account for all must be paid on the period, we need to remove what
        # has already been paid (or at least billed)
        self.compensate_existing_moves_on_period(work_set)

        # Schedule the payments depending on the chosen rule
        self.apply_payment_rule(work_set)

        work_set['move'].lines = work_set['lines'].values() + \
            work_set['counterparts']
        if work_set['total_amount'] > 0:
            work_set['move'].save()
            return work_set['move']
        else:
            return

    def bill_and_post(self, post=True):
        Move = Pool().get('account.move')
        Move.delete(Move.search([
                ('origin', '=', utils.convert_to_reference(self)),
                ('state', '=', 'draft'),
                ]))
        Transaction().cursor.commit()
        move = self.bill()
        if move and post:
            self.next_billing_date = coop_date.add_day(
                move.billing_period.end_date, 1)
            self.save()
            if not move.lines:
                Move.delete([move])
            else:
                Move.post([move])

    def generate_first_bill(self):
        if self.next_billing_date:
            self.next_billing_date = self.start_date
        self.bill_and_post(post=False)

    def calculate_price_at_date(self, date):
        cur_dict = {
            'date': date,
            'appliable_conditions_date': self.appliable_conditions_date}
        self.init_dict_for_rule_engine(cur_dict)
        prices, errs = self.offered.get_result('total_price', cur_dict)
        return (prices, errs)

    def calculate_prices_between_dates(self, start=None, end=None):
        if not start:
            start = self.start_date
        prices = []
        errs = []
        dates = self.get_dates()
        dates = utils.limit_dates(dates, self.start_date)
        for cur_date in dates:
            price, err = self.calculate_price_at_date(cur_date)
            if price:
                prices.extend(price)
            errs += err
        return prices, errs

    def get_last_bill(self, name):
        Move = Pool().get('account.move')
        try:
            result = [Move.search(
                [('origin', '=', utils.convert_to_reference(self))])[0].id]
            return result
        except:
            return []

    def get_total_price_at_date(self, at_date):
        return sum(map(lambda x: x.amount, filter(
            lambda x: x.start_date <= at_date and (
                not x.end_date or x.end_date >= at_date), self.prices)))

    def finalize_contract(self):
        super(Contract, self).finalize_contract()
        self.bill_and_post()

    def renew(self):
        res = super(Contract, self).renew()
        if not res:
            return res
        self.bill_and_post()
        return True

    def re_bill_from_date(self, at_date):
        '''Recalculate a new bill for a period when a modifiction has occured
        in the past and the previous bills already posted may be false'''
        if self.next_billing_date:
            self.next_billing_date = at_date
        self.bill_and_post()

    def temp_endorsment_re_bill(self):
        #TODO :Temporay while we don't have the endorsement date
        self.re_bill_from_date(self.start_date)

    # From account => party
    @classmethod
    def get_receivable_today(cls, contracts, name):
        res = {}
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        res = dict((p.id, Decimal('0.0')) for p in contracts)

        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        user = User(user_id)
        if not user.company:
            return res

        move_line = MoveLine.__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()
        line_query, _ = MoveLine.query_get(move_line)

        query_table = move.join(move_line,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))
        today_query = (move_line.maturity_date <= Date.today()) | (
            move_line.maturity_date == None)
        good_moves_query = move.id.in_(move.select(move.id, where=(
                    move.origin.in_(
                        ['contract.contract,%s' % x.id for x in contracts]))))

        cursor.execute(*query_table.select(move.origin, Sum(
                Coalesce(move_line.debit, 0) - Coalesce(move_line.credit, 0)),
                where=(account.active)
                & (account.kind == 'receivable')
                & good_moves_query
                & (move_line.reconciliation == None)
                & line_query
                & today_query
                & (account.company == user.company.id),
                group_by=(move.origin)))
        for contract_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[int(contract_id.split(',')[1])] = sum
        return res

    @classmethod
    def search_receivable_today(cls, name, clause):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Company = pool.get('company.company')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        if name not in ('receivable', 'payable',
                'receivable_today', 'payable_today'):
            raise Exception('Bad argument')

        company_id = None
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        user = User(user_id)
        if Transaction().context.get('company'):
            child_companies = Company.search([
                    ('parent', 'child_of', [user.main_company.id]),
                    ])
            if Transaction().context['company'] in child_companies:
                company_id = Transaction().context['company']

        if not company_id:
            if user.company:
                company_id = user.company.id
            elif user.main_company:
                company_id = user.main_company.id

        if not company_id:
            return []

        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]

        move_line = MoveLine.__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()
        line_query, _ = MoveLine.query_get(move_line)

        query_table = move.join(move_line,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))
        today_query = (move_line.maturity_date <= Date.today()) | (
            move_line.maturity_date == None)

        code = name
        today_query = True
        if name in ('receivable_today', 'payable_today'):
            code = name[:-6]
            today_query = (move_line.maturity_date <= Date.today()) | (
                move_line.maturity_date == None)

        cursor.execute(*query_table.select(move.contract,
                where=(account.active)
                & (account.kind == code)
                & (move_line.reconciliation == None)
                & line_query
                & today_query
                & (account.company == Company(company_id)),
                group_by=(move_line.party),
                having=Operator(Sum(
                        Coalesce(move_line.debit, 0) -
                        Coalesce(move_line.credit, 0)),
                    getattr(cls, name).sql_format(value))))

        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def get_var_names_for_full_extract(cls):
        res = super(Contract, cls).get_var_names_for_full_extract()
        res.extend(['billing_managers'])
        return res

    def get_use_prices(self, name):
        if not self.offered:
            return False
        for rules in self.offered.pricing_rules:
            return True
        for option in self.options:
            if option.offered.pricing_rules:
                return True
        return False


class Option():
    'Option'

    __metaclass__ = PoolMeta
    __name__ = 'contract.subscribed_option'

    def get_name_for_billing(self):
        return self.get_coverage().name + ' - Base Price'


class CoveredElement():
    'Covered Element'

    __metaclass__ = PoolMeta
    __name__ = 'ins_contract.covered_element'

    subscriber = fields.Function(
        fields.Many2One('party.party', 'Subscriber'),
        'get_subscriber_id')
    indemnification_bank_account = fields.Many2One('bank.account',
        'Indemnification Bank Account',
        states={'invisible': ~Eval('is_person')},
        depends=['item_kind', 'party', 'subscriber'],
        domain=[
            ['OR',
                ('owners', '=', Eval('subscriber')),
                If(IS_PARTY, ('owners', '=', Eval('party', 0)), ())]])

    def get_name_for_billing(self):
        return self.get_rec_name('billing')

    def get_subscriber_id(self, name):
        return self.main_contract.subscriber.id


class CoveredData():
    'Covered Data'

    __metaclass__ = PoolMeta
    __name__ = 'ins_contract.covered_data'

    def get_name_for_billing(self):
        return self.covered_element.get_name_for_billing()


class TaxDesc():
    'Tax Desc'

    __metaclass__ = PoolMeta
    __name__ = 'coop_account.tax_desc'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('company', '=', Eval('context', {}).get('company'))],
        required=True)
    company = fields.Function(
        fields.Many2One('company.company', 'Company',
            depends=['account_for_billing']),
        'get_company', searcher='search_company')

    @classmethod
    def __setup__(cls):
        super(TaxDesc, cls).__setup__()
        cls.account_for_billing = copy.copy(cls.account_for_billing)
        cls.account_for_billing.domain = export.clean_domain_for_import(
            cls.account_for_billing.domain)

    def get_account_for_billing(self):
        return self.account_for_billing

    def get_company(self, name):
        if not (hasattr(self, 'account_for_billing') and
                self.account_for_billing):
            return None
        return self.account_for_billing.company

    @classmethod
    def search_company(cls, name, clause):
        return [(('account_for_billing.company',) + tuple(clause[1:]))]


class FeeDesc():
    'Fee Desc'

    __metaclass__ = PoolMeta
    __name__ = 'coop_account.fee_desc'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', depends=['company'], domain=[
            ('company', '=', Eval('context', {}).get('company'))],
        required=True)
    company = fields.Function(
        fields.Many2One('company.company', 'Company',
            depends=['account_for_billing']),
        'get_company', searcher='search_company')

    @classmethod
    def __setup__(cls):
        super(FeeDesc, cls).__setup__()
        cls.account_for_billing = copy.copy(cls.account_for_billing)
        cls.account_for_billing.domain = export.clean_domain_for_import(
            cls.account_for_billing.domain)

    def get_account_for_billing(self):
        return self.account_for_billing

    def get_company(self, name):
        if not (hasattr(self, 'account_for_billing') and
                self.account_for_billing):
            return None
        return self.account_for_billing.company

    @classmethod
    def search_company(cls, name, clause):
        return [(('account_for_billing.company',) + tuple(clause[1:]))]


class Sequence():
    'Sequence'

    __metaclass__ = PoolMeta
    __name__ = 'ir.sequence'

    @classmethod
    def __setup__(cls):
        super(Sequence, cls).__setup__()
        cls.company = copy.copy(cls.company)
        cls.company.domain = export.clean_domain_for_import(
            cls.company.domain, 'company')


class Company(export.ExportImportMixin):
    'Company'

    __metaclass__ = PoolMeta
    __name__ = 'company.company'

    fiscal_years = fields.One2Many('account.fiscalyear', 'company',
        'Fiscal Years')

    def _post_import_set_default_accounts(self):
        account_configuration = Pool().get('account.configuration')(0)
        AccountType = Pool().get('account.account.type')
        Account = Pool().get('account.account')
        for name in ('receivable', 'payable'):
            if getattr(account_configuration, 'default_account_%s' % name):
                continue
            account_type = AccountType()
            account_type.name = 'Client %s' % name
            account_type.company = self
            account_type.save()
            account = Account()
            account.company = self
            account.type = account_type
            account.name = 'Default %s account' % name
            account.kind = name
            account.save()
            setattr(account_configuration, 'default_account_%s' % name,
                account)
        account_configuration.save()

    @classmethod
    def __post_import(cls, companies):
        for company in companies:
            with Transaction().set_context(company=company.id):
                company._post_import_set_default_accounts()

    @classmethod
    def _export_force_recreate(cls):
        result = super(Company, cls)._export_force_recreate()
        result.remove('fiscal_years')
        return result

    @classmethod
    def _export_keys(cls):
        return set(['party.name'])


class FiscalYear(export.ExportImportMixin):
    'Fiscal Year'

    __metaclass__ = PoolMeta
    __name__ = 'account.fiscalyear'

    @classmethod
    def __setup__(cls):
        super(FiscalYear, cls).__setup__()
        cls.company = copy.copy(cls.company)
        cls.company.domain = export.clean_domain_for_import(
            cls.company.domain, 'company')

    @classmethod
    def _export_skips(cls):
        result = super(FiscalYear, cls)._export_skips()
        result.add('close_lines')
        return result

    @classmethod
    def _export_force_recreate(cls):
        res = super(FiscalYear, cls)._export_force_recreate()
        res.remove('periods')
        return res

    @classmethod
    def _export_keys(cls):
        return set(['company.party.name', 'code'])


class Period(export.ExportImportMixin):
    'Period'

    __metaclass__ = PoolMeta
    __name__ = 'account.period'

    @classmethod
    def write(cls, periods, vals):
        # Overwritten to check for moves only if start_date / end_date /
        # fiscalyear actually changes
        found = [x for x in ('start_date', 'end_date', 'fiscalyear')
                if x in vals]
        if not found:
            return super(Period, cls).write(periods, vals)
        for period in periods:
            if ('start_date' in found and period.start_date !=
                    vals['start_date']) or ('end_date' in found and
                    period.end_date != vals['end_date']) or (
                    'fiscalyear' in found and period.fiscalyear.id !=
                        vals['fiscalyear']):
                if period.moves:
                    cls.raise_user_error('modify_del_period_moves', (
                        period.rec_name))
        for x in found:
            del vals[x]
        return super(Period, cls).write(periods, vals)

    @classmethod
    def _export_keys(cls):
        return set(['code', 'fiscalyear.code',
                'fiscalyear.company.party.name'])

    def check_dates(self):
        if not '__importing__' in Transaction().context:
            return super(Period, self).check_dates()
        return True
