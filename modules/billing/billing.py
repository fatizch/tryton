import copy
import datetime
from collections import defaultdict
from itertools import repeat, izip, chain

from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, If, Date

from trytond.modules.coop_utils import model, fields, utils, date, coop_string
from trytond.modules.coop_utils import export
from trytond.modules.insurance_product.business_rule.pricing_rule import \
    PRICING_FREQUENCY
from trytond.modules.insurance_contract.contract import IS_PARTY

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
]

PAYMENT_MODES = [
    ('cash', 'Cash'),
    ('check', 'Check'),
    ('wire_transfer', 'Wire Transfer'),
    ('direct_debit', 'Direct Debit'),
]

export.add_export_to_model([
    ('account.account', ('code', 'name')),
    ('company.company', ('party.code', )),
    ('account.tax', ('name', )),
    ('account.account.type', ('name', )),
])


class PaymentMethod(model.CoopSQL, model.CoopView):
    'Payment Method'

    __name__ = 'billing.payment_method'

    name = fields.Char('Name')
    code = fields.Char('Code', required=True, on_change_with=['code', 'name'])
    payment_rule = fields.Many2One('billing.payment_rule', 'Payment Rule',
        ondelete='RESTRICT', required=True)
    payment_mode = fields.Selection(PAYMENT_MODES, 'Payment Mode',
        required=True)

    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)


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

    def get_short_name(self, name):
        if self.on_object:
            return self.on_object.get_name_for_billing()
        return 'Main Line'

    def init_values(self):
        if not hasattr(self, 'name') or not self.name:
            self.name = ''
        self.amount = 0
        self.all_lines = []

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

    def init_from_result_line(self, line):
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
            if (detail.on_object and detail.on_object.__name__ ==
                    'ins_product.pricing_component' and
                    detail.on_object.kind in ('tax', 'fee')):
                continue
            detail_line = PriceLineModel()
            detail_line.init_from_result_line(detail)
            self.all_lines.append(detail_line)
        if not line.details:
            self.amount = line.amount
        else:
            self.amount = sum(map(lambda x: x.amount, self.all_lines))

    def build_tax_lines(self, line):
        def get_tax_details(line, taxes):
            for elem in line.details:
                if (elem.on_object and elem.on_object.__name__ ==
                        'ins_product.pricing_component' and
                        elem.on_object.kind == 'tax'):
                    if elem.on_object.tax.id in taxes:
                        taxes[elem.on_object.tax.id].append(elem)
                    else:
                        taxes[elem.on_object.tax.id] = [elem]
                else:
                    get_tax_details(elem, taxes)

        tax_details = {}
        if not (hasattr(self, 'tax_lines') and self.tax_lines):
            self.tax_lines = []
        get_tax_details(line, tax_details)
        TaxDesc = Pool().get('coop_account.tax_desc')
        TaxRelation = Pool().get('billing.price_line-tax-relation')
        for tax_id, tax_lines in tax_details.iteritems():
            the_tax = TaxDesc(tax_id)
            tax_relation = TaxRelation()
            tax_relation.tax_desc = the_tax
            tax_relation.to_recalculate = tax_lines[0].to_recalculate
            tax_relation.amount = sum(map(lambda x: x.amount, tax_lines))
            self.tax_lines.append(tax_relation)

    def build_fee_lines(self, line):
        def get_fee_details(line, fees):
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
                        get_fee_details(detail, fees)

        fee_details = {}
        if not (hasattr(self, 'fee_lines') and self.fee_lines):
            self.fee_lines = []
        get_fee_details(line, fee_details)
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
        final_date = date.add_frequency(self.frequency, at_date)
        return date.number_of_days_between(at_date, final_date) - 1

    def get_currency(self):
        if self.contract:
            return self.contract.currency
        elif self.master:
            return self.master.currency


class BillingManager(model.CoopSQL, model.CoopView):
    'Billing Manager'
    '''
        This object will manage all billing-related content on the contract.
        It will be the target of all sql requests for automated bill
        calculation, lapsing, etc...
    '''
    __name__ = 'billing.billing_manager'

    contract = fields.Many2One('contract.contract', 'Contract')
    policy_owner = fields.Function(
        fields.Many2One('party.party', 'Party', states={'invisible': True}),
        'get_policy_owner_id')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    payment_method = fields.Many2One('billing.payment_method',
        'Payment Method')
    payment_mode = fields.Function(
        fields.Char('Payment Mode', states={'invisible': True},
            on_change_with=['payment_method']),
        'on_change_with_payment_mode')
    payment_bank_account = fields.Many2One('party.bank_account',
        'Payment Bank Account',
        states={'invisible': Eval('payment_mode') != 'direct_debit'},
        domain=[('party', '=', Eval('policy_owner'))],
        depends=['policy_owner'])
    disbursment_bank_account = fields.Many2One('party.bank_account',
        'Disbursement Bank Account',
        states={'invisible': Eval('payment_mode') != 'direct_debit'},
        domain=[('party', '=', Eval('policy_owner'))],
        depends=['policy_owner'])

    @classmethod
    def __setup__(cls):
        super(BillingManager, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))

    def init_from_contract(self, contract, start_date):
        self.start_date = start_date
        self.payment_method = contract.offered.get_default_payment_method()

    def on_change_with_payment_mode(self, name=None):
        if not (hasattr(self, 'payment_method') and self.payment_method):
            return ''
        return self.payment_method.payment_mode

    def get_policy_owner_id(self, name):
        policy_owner = (self.contract.get_policy_owner(self.start_date)
            if self.contract else None)
        return policy_owner.id if policy_owner else None


class BillingPeriod(model.CoopSQL, model.CoopView):
    'Billing Period'
    __name__ = 'billing.period'
    contract = fields.Many2One('contract.contract', 'Contract', required=True)
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
        ref = (self.contract.contract_number
            if self.contract.contract_number else self.contract.rec_name)
        return '%s (%s - %s)' % (ref, self.start_date, self.end_date)

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('contract',), tuple(clause[1:])]

    @classmethod
    def validate(cls, periods):
        for period in periods:
            period.check_dates()

    def check_dates(self):
        cursor = Transaction().cursor
        cursor.execute('SELECT id '
            'FROM "' + self._table + '" '
            'WHERE ((start_date <= %s AND end_date >= %s) '
                'OR (start_date <= %s AND end_date >= %s) '
                'OR (start_date >= %s AND end_date <= %s)) '
            'AND id != %s AND contract = %s',
            (self.start_date, self.start_date,
                self.end_date, self.end_date,
                self.start_date, self.end_date,
                self.id, self.contract.id))
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
        'billing.bill_parameters_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Preview', 'bill_display', 'tryton-go-next')])
    bill_display = StateView(
        'billing.billing_process.bill_display',
        'billing.bill_display_form', [
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
        contract.next_billing_date = date.add_day(move_date, 1)
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
    is_default = fields.Boolean('Default')


class Product():
    'Product'

    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    payment_methods = fields.One2Many(
        'billing.product-payment_method-relation', 'product',
        'Payment Methods')
    account_for_billing = fields.Many2One('account.account',
        'Account for billing', required=True,
        domain=[('kind', '=', 'revenue')])

    def get_default_payment_method(self):
        for elem in self.payment_methods:
            if elem.is_default:
                return elem.payment_method

    def get_allowed_payment_methods(self):
        result = []
        for elem in self.payment_methods:
            result.append(elem.payment_method)
        return result

    def get_account_for_billing(self):
        return self.account_for_billing


class Coverage():
    'Coverage'

    __metaclass__ = PoolMeta
    __name__ = 'offered.coverage'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', domain=[('kind', '=', 'revenue')], states={
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
    next_billing_date = fields.Date('Next Billing Date')
    prices = fields.One2Many(
        'billing.price_line', 'contract', 'Prices')
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
                'button_calculate_prices': {},
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

    def next_billing_period(self):
        start_date = self.next_billing_date
        last_date = date.add_day(self.start_date, -1)
        if not utils.is_none(self, 'billing_periods'):
            for period in self.billing_periods:
                if (start_date >= period.start_date and (
                        not period.end_date or period.end_date >= start_date)):
                    return (period.start_date, period.end_date)
            if period.end_date > last_date:
                last_date = period.end_date
        new_period_start = date.add_day(last_date, 1)
        new_period_end = date.add_frequency(
            self.get_product_frequency(last_date), last_date)
        if self.next_renewal_date:
            new_period_end = min(new_period_end, date.add_day(
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
            price_line.init_from_result_line(price)
            price_line.build_tax_lines(price)
            price_line.build_fee_lines(price)
            try:
                price_line.end_date = dates[dates.index(price_line.start_date)
                    + 1] + datetime.timedelta(days=-1)
            except IndexError:
                pass
            result_prices.append(price_line)
        for elem in oldest:
            elem.end_date = date.add_day(dates[0], -1)
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

    def bill(self, *period):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        BillingPeriod = pool.get('billing.period')

        if not period:
            period = self.next_billing_period()
        if not period:
            return
        billing_date = period[0]
        for billing_period in self.billing_periods \
                if hasattr(self, 'billing_periods') else []:
            if (billing_period.start_date, billing_period.end_date) == period:
                break
        else:
            billing_period = BillingPeriod(contract=self)
            billing_period.start_date, billing_period.end_date = period
            billing_period.save()

        price_lines = self.create_price_list(*period)

        self.init_billing_manager()
        billing_manager = self.get_billing_manager(billing_date)

        assert billing_manager, 'Missing Billing Manager'

        try:
            payment_rule = billing_manager.payment_method.payment_rule
        except:
            payment_rule = None
        currency = self.get_currency()

        period_id = Period.find(self.company.id, date=billing_date)

        move = Move(
            journal=self.get_journal(),
            period=period_id,
            date=billing_date,
            origin=utils.convert_to_reference(self),
            billing_period=billing_period,
            )

        lines = defaultdict(lambda: Line(credit=0, debit=0))
        total_amount = 0
        taxes = defaultdict(
            lambda: {'amount': 0, 'base': 0, 'to_recalculate': False})
        fees = defaultdict(
            lambda: {'amount': 0, 'base': 0, 'to_recalculate': False})
        for period, price_line in price_lines:
            number_of_days = date.number_of_days_between(*period)
            price_line_days = price_line.get_number_of_days_at_date(period[0])
            convert_factor = number_of_days / Decimal(price_line_days)
            amount = price_line.amount * convert_factor
            amount = currency.round(amount)
            account = price_line.get_account_for_billing()

            line = lines[(price_line.on_object, account)]
            line.second_origin = price_line.on_object
            line.credit += amount
            line.account = account
            line.party = self.subscriber

            total_amount += amount

            for type_, sub_lines, sub_line in chain(
                    izip(repeat('tax'), repeat(taxes), price_line.tax_lines),
                    izip(repeat('fee'), repeat(fees), price_line.fee_lines)):
                desc = getattr(sub_line, '%s_desc' % type_)
                values = sub_lines[desc.id]
                values['object'] = desc
                values['to_recalculate'] |= sub_line.to_recalculate
                values['amount'] += sub_line.amount * convert_factor
                values['base'] += amount

        if payment_rule and payment_rule.appliable_fees:
            for fee_desc in payment_rule.appliable_fees:
                fee_line = fees[fee_desc.id]
                fee_line['object'] = fee_desc
                fee_line['to_recalculate'] = True
                fee_line['amount'] = 0
                fee_line['base'] = total_amount

        for type_, data in chain(
                izip(repeat('tax'), taxes.itervalues()),
                izip(repeat('fee'), fees.itervalues())):
            account = data['object'].get_account_for_billing()
            line = lines[(data['object'], account)]
            line.party = self.subscriber
            line.account = account
            if data['to_recalculate']:
                good_version = data['object'].get_version_at_date(
                    period[0])
                amount = getattr(good_version,
                    'apply_%s' % type_)(data['base'])
            else:
                amount = data['amount']
            line.second_origin = data['object']
            line.credit = currency.round(amount)
            total_amount += amount

        if billing_period.moves:
            print utils.format_data(lines)
            for old_move in billing_period.moves:
                if old_move.state == 'draft':
                    continue
                for old_line in old_move.lines:
                    if old_line.account == self.subscriber.account_receivable:
                        continue
                    print old_line.credit
                    print old_line.debit
                    print old_line.second_origin
                    line = lines[(old_line.second_origin, old_line.account)]
                    line.second_origin = old_line.second_origin
                    line.account = old_line.account
                    if old_line.credit:
                        line.credit -= old_line.credit
                        total_amount -= old_line.credit
                    else:
                        line.credit += old_line.debit
                        total_amount += old_line.debit
            print utils.format_data(lines)
            Move.delete(
                [x for x in billing_period.moves if x.state == 'draft'])

        for line in lines.itervalues():
            if line.credit < 0:
                line.credit, line.debit = 0, -line.credit

        if total_amount >= 0 and payment_rule:
            term_lines = payment_rule.compute(billing_date, period[1],
                total_amount, currency)
        else:
            term_lines = [(Date.today(), currency.round(total_amount))]
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

        move.lines = lines.values() + counterparts
        move.save()
        return move

    def bill_and_post(self, post=True):
        Move = Pool().get('account.move')
        Move.delete(Move.search([
                ('origin', '=', utils.convert_to_reference(self)),
                ('state', '=', 'draft'),
                ]))
        Transaction().cursor.commit()
        move = self.bill()
        if move and post:
            if not move.lines:
                Move.delete([move])
            else:
                Move.post([move])
            self.next_billing_date = date.add_day(
                move.billing_period.end_date, 1)
            self.save()

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
        company_id = user.company.id

        line_query, _ = MoveLine.query_get()

        today_query = 'AND (l.maturity_date <= %s ' \
            'OR l.maturity_date IS NULL) '
        today_value = [Date.today()]

        cursor.execute('SELECT m.origin, '
                'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) '
            'FROM account_move_line AS l, account_account AS a '
            ', account_move as m '
            'WHERE a.id = l.account '
                'AND a.active '
                'AND a.kind = \'receivable\' '
                'AND l.move = m.id '
                'AND m.id IN '
                    '(SELECT m.id FROM account_move as m '
                    'WHERE m.origin IN '
                    '(' + ','.join(('%s',) * len(contracts)) + ')) '
                'AND l.reconciliation IS NULL '
                'AND ' + line_query + ' '
                + today_query +
                'AND a.company = %s '
            'GROUP BY m.origin',
            [utils.convert_to_reference(p) for p in contracts] +
            today_value + [company_id])
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

        code = name
        today_query = ''
        today_value = []
        if name in ('receivable_today', 'payable_today'):
            code = name[:-6]
            today_query = 'AND (l.maturity_date <= %s ' \
                'OR l.maturity_date IS NULL) '
            today_value = [Date.today()]

        line_query, _ = MoveLine.query_get()

        cursor.execute('SELECT m.contract '
            'FROM account_move_line AS l, account_account AS a '
            ', account_move as m '
            'WHERE a.id = l.account '
                'AND a.active '
                'AND a.kind = %s '
                'AND l.move = m.id '
                'AND l.reconciliation IS NULL '
                'AND ' + line_query + ' '
                + today_query +
                'AND a.company = %s '
            'GROUP BY l.party '
            'HAVING (SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) '
                + clause[1] + ' %s)',
            [code] + today_value + [company_id] + [Decimal(clause[2] or 0)])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]


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

    indemnification_bank_account = fields.Many2One('party.bank_account',
        'Indemnification Bank Account',
        depends=['contract', 'item_kind', 'party'],
        domain=[
            ['OR',
                ('party', '=', Eval('_parent_contract', {}).get('subscriber')),
                If(IS_PARTY, ('party', '=', Eval('party', 0)), ())]])

    def get_name_for_billing(self):
        return self.get_rec_name('billing')


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
        'Account for billing', required=True)

    def get_account_for_billing(self):
        return self.account_for_billing


class FeeDesc():
    'Fee Desc'

    __metaclass__ = PoolMeta
    __name__ = 'coop_account.fee_desc'

    account_for_billing = fields.Many2One('account.account',
        'Account for billing', required=True)

    def get_account_for_billing(self):
        return self.account_for_billing


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
