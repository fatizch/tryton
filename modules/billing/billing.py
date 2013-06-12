import copy
import datetime
from collections import defaultdict
from itertools import repeat, izip, chain

from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, If

from trytond.modules.coop_utils import model, fields, utils, date, coop_string
from trytond.modules.coop_utils import export
from trytond.modules.insurance_product.business_rule.pricing_rule import \
    PRICING_FREQUENCY
from trytond.modules.insurance_contract.contract import IS_PARTY
from trytond.modules.offered.offered import DEF_CUR_DIG

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
    'Contract',
    'Option',
    'CoveredElement',
    'CoveredData',
    'PaymentTerm',
    'TaxDesc',
    'FeeDesc',
    'Party',
]

PAYMENT_MODES = [
    ('cash', 'Cash'),
    ('check', 'Check'),
    ('wire_transfer', 'Wire Transfer'),
    ('direct_debit', 'Direct Debit'),
]

export.add_export_to_model([
    ('account.invoice.payment_term', ('name', )),
    ('account.invoice.payment_term.line', ()),
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
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', ondelete='RESTRICT')
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


class PriceLineFeeRelation(model.CoopSQL, model.CoopView):
    'Price Line Fee Relation'

    __name__ = 'billing.price_line-fee-relation'

    price_line = fields.Many2One('billing.price_line', 'Price Line',
        ondelete='CASCADE')
    fee_desc = fields.Many2One('coop_account.fee_desc', 'Fee',
        ondelete='RESTRICT')
    to_recalculate = fields.Boolean('Recalculate at billing')
    amount = fields.Numeric('Amount')


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
        # TODO
        Account = Pool().get('account.account')
        accounts = Account.search([
                ('kind', '=', 'revenue'),
                ], limit=1)
        if accounts:
            return accounts[0]

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
        return self.contract.rec_name

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

    def get_default_payment_method(self):
        for elem in self.payment_methods:
            if elem.is_default:
                return elem.payment_method

    def get_allowed_payment_methods(self):
        result = []
        for elem in self.payment_methods:
            result.append(elem.payment_method)
        return result


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

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._buttons.update({
                'button_calculate_prices': {},
                })

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

    def next_billing_period(self):
        last_date = self.start_date
        for period in self.billing_periods:
            if (self.start_date <= period.start_date and (
                    not period.end_date
                    or period.end_date >= self.start_date)):
                return (period.start_date, period.end_date)
            if period.end_date > last_date:
                last_date = period.end_date
        new_period_start = date.add_day(last_date, 1)
        new_period_end = date.add_frequency(
            self.get_product_frequency(last_date), last_date)
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
        to_delete = []
        if hasattr(self, 'prices') and self.prices:
            for price in self.prices:
                to_delete.append(price)
        result_prices = []
        dates = list(set([elem.start_date for elem in prices]))
        dates.sort()
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
        self.prices = result_prices
        self.save()

        PriceLine.delete(to_delete)

    @classmethod
    @model.CoopView.button
    def button_calculate_prices(cls, contracts):
        for contract in contracts:
            contract.calculate_prices()

    def calculate_prices(self):
        prices, errs = self.calculate_prices_at_all_dates()

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
        billing_date = period[0]
        for billing_period in self.billing_periods:
            if (billing_period.start_date, billing_period.end_date) == period:
                break
        else:
            billing_period = BillingPeriod(contract=self)
            billing_period.start_date, billing_period.end_date = period
            billing_period.save()

        price_lines = self.create_price_list(*period)

        self.init_billing_manager()
        billing_manager = None
        for manager in self.billing_managers:
            if (manager.start_date <= billing_date
                    and (manager.end_date is None
                        or manager.end_date >= billing_date)):
                billing_manager = manager
                break

        assert billing_manager, 'Missing Billing Manager'

        payment_term = billing_manager.payment_method.payment_term
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

        for type_, data in chain(
                izip(repeat('tax'), taxes.itervalues()),
                izip(repeat('fee'), fees.itervalues())):
            account = data['object'].get_account_for_billing()
            line = lines[(None, account)]
            line.party = self.subscriber
            line.account = account
            if data['to_recalculate']:
                good_version = data['object'].get_version_at_date(
                    period[0])
                amount = getattr(good_version,
                    'apply_%s' % type_)(data['base'])
            else:
                amount = data['amount']
            line.credit = currency.round(amount)
            total_amount += amount

        if billing_period.moves:
            for old_move in billing_period.moves:
                for old_line in old_move.lines:
                    if old_line.account == self.subscriber.account_receivable:
                        continue
                    line = lines[(old_line.second_origin, old_line.account)]
                    line.second_origin = old_line.second_origin
                    line.account = old_line.account
                    if old_line.credit:
                        line.credit -= old_line.credit
                        total_amount -= old_line.credit
                    else:
                        line.credit += old_line.debit
                        total_amount += old_line.debit

        for line in lines.itervalues():
            if line.credit < 0:
                line.credit, line.debit = 0, -line.credit

        if total_amount >= 0 and payment_term:
            term_lines = payment_term.compute(total_amount, currency,
                billing_date)
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


class PaymentTerm():
    'Payment Term'

    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.payment_term'

    def check_remainder(self):
        if Transaction().context.get('__importing__'):
            return True
        return super(PaymentTerm, self).check_remainder()


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


class Party():
    'Party'

    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()

        # Hack to remove constraints when importing
        # TODO : Be cleaner
        def remove_company(domain):
            to_remove = []
            for i, elem in enumerate(domain):
                if elem[0] == 'company' and elem[1] == '=':
                    to_remove.insert(0, i)
            for i in to_remove:
                domain.pop(i)

        cls.account_payable = copy.copy(cls.account_payable)
        remove_company(cls.account_payable.domain)
        cls.account_receivable = copy.copy(cls.account_receivable)
        remove_company(cls.account_receivable.domain)
