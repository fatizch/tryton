import datetime

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, If

from trytond.modules.coop_utils import model, fields, utils, date, abstract
from trytond.modules.coop_utils import export
from trytond.modules.insurance_product import product
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
    'GenericBillLine',
    'Bill',
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
])


class PaymentMethod(model.CoopSQL, model.CoopView):
    'Payment Method'

    __name__ = 'billing.payment_method'

    name = fields.Char('Name')
    code = fields.Char('Code', required=True)
    payment_term = fields.Many2One('account.invoice.payment_term',
        'Payment Term', ondelete='RESTRICT')
    payment_mode = fields.Selection(PAYMENT_MODES, 'Payment Mode',
        required=True)


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
                print elem.on_object
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
            f('ins_product.product'),
            f('ins_product.coverage'),
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
        return date.number_of_days_between(at_date, final_date)


class BillingManager(model.CoopSQL, model.CoopView):
    'Billing Manager'
    '''
        This object will manage all billing-related content on the contract.
        It will be the target of all sql requests for automated bill
        calculation, lapsing, etc...
    '''
    __name__ = 'billing.billing_manager'

    contract = fields.Many2One('contract.contract', 'Contract')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    payment_method = fields.Many2One('billing.payment_method',
        'Payment Method', required=True)
    payment_mode = fields.Function(
        fields.Char('Payment Mode', states={'invisible': True},
            on_change_with=['payment_method']),
        'on_change_with_payment_mode')
    payment_bank_account = fields.Many2One('party.bank_account',
        'Payment Bank Account', depends=['payment_mode'],
        states={'invisible': Eval('payment_mode') != 'direct_debit'})

    @classmethod
    def __setup__(cls):
        super(BillingManager, cls).__setup__()
        cls._order.insert(0, ('start_date', 'ASC'))

    def on_change_with_payment_mode(self, name=None):
        if not (hasattr(self, 'payment_method') and self.payment_method):
            return ''
        return self.payment_method.payment_mode


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
            'AND id != %s',
            (self.start_date, self.start_date,
                self.end_date, self.end_date,
                self.start_date, self.end_date,
                self.id))
        second_id = cursor.fetchone()
        if second_id:
            second = self.__class__(second_id[0])
            self.raise_user_error('period_overlaps', {
                    'first': self.rec_name,
                    'second': second.rec_name,
                    })


class GenericBillLine(model.CoopSQL, model.CoopView):
    'Bill Line'

    __name__ = 'billing.billing.generic_line'

    name = fields.Char('Short Description')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    amount_ht = fields.Numeric('Amount HT')
    amount_ttc = fields.Numeric('Amount TTC')
    base_price = fields.Numeric('Base Price')
    on_object = fields.Reference('Target', 'get_on_object_model')
    master = fields.Reference(
        'Master',
        [('billing.billing.bill', 'Bill'),
            ('billing.billing.generic_line', 'Line')])
    kind = fields.Selection([
        ('main', 'Node'),
        ('base', 'Base Amount'),
        ('tax', 'Tax'),
        ('fee', 'Fee')], 'Kind')
    childs = fields.One2Many(
        'billing.billing.generic_line', 'master', 'Child Lines')
    node_childs = fields.Function(
        fields.One2Many(
            'billing.billing.generic_line', None, 'Nodes'),
        'get_node_childs')
    detail_childs = fields.Function(
        fields.One2Many(
            'billing.billing.generic_line', None, 'Details'),
        'get_detail_childs')

    @staticmethod
    def get_on_object_model():
        f = lambda x: (x, x)
        res = [
            f(''),
            f('ins_product.product'),
            f('ins_product.coverage'),
            f('contract.contract'),
            f('contract.subscribed_option')]
        res += utils.get_descendents('ins_contract.covered_data')
        return res

    def get_detail_childs(self, name):
        res = []
        for elem in self.childs:
            if elem.kind != 'main':
                res.append(elem)
        return abstract.WithAbstract.serialize_field(res)

    def get_node_childs(self, name):
        res = []
        for elem in self.childs:
            if elem.kind == 'main':
                res.append(elem)
        return abstract.WithAbstract.serialize_field(res)

    def flat_init(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        self.amount_ht = 0
        self.amount_ttc = 0
        self.base_price = 0
        self.name = ''

    def update_from_price_line(self, line, number_of_days, base_days):
        LineModel = Pool().get(self.__name__)
        self.childs = []
        for elem in line.all_lines:
            sub_line = LineModel()
            sub_line.flat_init(self.start_date, self.end_date)
            sub_line.update_from_price_line(elem, number_of_days, base_days)
            self.childs.append(sub_line)
        if line.kind != 'tax':
            self.amount_ht = line.amount * number_of_days / base_days
            self.amount_ttc = self.amount_ht + line.get_total_detail('tax') \
                * number_of_days / base_days
        else:
            self.amount_ht = 0
            self.amount_ttc = line.amount * number_of_days / base_days
        self.base_price = line.amount
        self.kind = line.kind
        self.name = line.get_id()
        self.on_object = line.on_object

    def get_rec_name(self, name):
        if hasattr(self, 'on_object') and self.on_object:
            return utils.convert_ref_to_obj(
                self.on_object).get_name_for_billing()
        if hasattr(self, 'name') and self.name:
            return self.kind + ' - ' + self.name
        return self.kind

    def is_main_line(self):
        return hasattr(self, 'on_object') and self.on_object and \
            self.on_object.split(',')[0] in (
                'ins_product.product',
                'ins_product.coverage')

    def get_total_detail(self, name):
        res = 0
        for line in self.detail_childs:
            if line.kind == name:
                res += line.amount_ht
        return res

    def get_number_of_days(self):
        return self.end_date.toordinal() - self.start_date.toordinal() + 1


class Bill(model.CoopSQL, model.CoopView):
    'Bill'

    __name__ = 'billing.billing.bill'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    amount_ht = fields.Numeric('Amount HT', required=True)
    amount_ttc = fields.Numeric('Amount TTC')
    lines = fields.One2Many(
        'billing.billing.generic_line', 'master', 'Bill Lines',
        order=[('start_date', 'ASC'), ('name', 'ASC')])
    contract = fields.Many2One('contract.contract', 'Contract')
    bill_details = fields.Function(
        fields.One2Many(
            'billing.billing.generic_line', None, 'Bill Details'),
        'get_bill_details')

    def get_bill_details(self, name):
        DetailLine = Pool().get('billing.billing.generic_line')
        existing = {}
        res = {}
        for line in self.lines:
            for elem in line.childs:
                if elem.kind != 'main':
                    if (elem.kind, elem.name) in existing:
                        good_line = existing[(elem.kind, elem.name)]
                        good_line.amount_ht += elem.amount_ht
                        good_line.amount_ttc += elem.amount_ttc
                    else:
                        new_line = DetailLine()
                        new_line.kind = elem.kind
                        new_line.name = elem.name
                        new_line.amount_ht = elem.amount_ht
                        new_line.amount_ttc = elem.amount_ttc
                        if elem.kind in res:
                            res[elem.kind].append(new_line)
                        else:
                            res[elem.kind] = [new_line]
                        existing[(elem.kind, elem.name)] = new_line
        details = []
        for k, v in res.iteritems():
            details.extend(v)
        return abstract.WithAbstract.serialize_field(details)

    def flat_init(self, start_date, end_date, contract):
        self.start_date = start_date
        self.end_date = end_date
        self.lines = []
        self.amount_ht = 0
        self.amount_ttc = 0
        self.contract = contract

    def append_bill_line(self, line):
        self.amount_ht += line.amount_ht
        self.amount_ttc += line.amount_ttc
        self.lines.append(line)

    def init_from_lines(self, lines):
        GenericBillLine = Pool().get('billing.billing.generic_line')
        for start_date, end_date, cur_line in lines:
            number_of_days = date.number_of_days_between(start_date, end_date)
            try:
                frequency_days, _ = cur_line.on_object.get_result(
                    'frequency_days',
                    {'date': start_date},
                    kind='pricing')
            except product.NonExistingRuleKindException:
                frequency_days = 365
            bill_line = GenericBillLine()
            bill_line.flat_init(start_date, end_date)
            bill_line.update_from_price_line(
                cur_line, number_of_days, frequency_days)
            self.append_bill_line(bill_line)


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
        bill_dates = contract.next_billing_dates()
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
        return 'end'


class ProductPaymentMethodRelation(model.CoopSQL, model.CoopView):
    'Product to Payment Method Relation definition'

    __name__ = 'billing.product-payment_method-relation'

    product = fields.Many2One('ins_product.product', 'Product',
        ondelete='CASCADE')
    payment_method = fields.Many2One('billing.payment_method',
        'Payment Method', ondelete='RESTRICT')
    is_default = fields.Boolean('Default')


class Product():
    'Product'

    __metaclass__ = PoolMeta
    __name__ = 'ins_product.product'

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

    def init_billing_manager(self):
        if not self.billing_managers:
            bm = self.new_billing_manager()
            bm.contract = self
            bm.start_date = self.start_date
            bm.payment_method = self.offered.get_default_payment_method()
            self.billing_managers = [bm]
            bm.save()

    def next_billing_dates(self):
        start_date = self.next_billing_date or self.start_date  # FIXME
        return (
            start_date,
            date.add_frequency(
                self.get_product_frequency(start_date), start_date))

    @classmethod
    def get_price_line_model(cls):
        return cls._fields['prices'].model_name

    def get_product_frequency(self, at_date):
        res, errs = self.offered.get_result(
            'frequency',
            {'date': at_date})
        if not errs:
            return res

    def get_bill_model(self):
        return 'billing.billing.bill'

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

    def bill(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        BillingPeriod = pool.get('billing.period')

        period = self.next_billing_dates()
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
            if (manager.start_date >= billing_date
                    and (not manager.end_date
                        or manager.end_date <= billing_date)):
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
            origin=str(self),
            billing_period=billing_period,
            )

        lines = []
        total_amount = 0
        taxes = {}
        fees = {}
        for period, price_line in price_lines:
            number_of_days = date.number_of_days_between(*period)
            price_line_days = price_line.get_number_of_days_at_date(period[0])
            convert_factor = number_of_days / price_line_days
            amount = price_line.amount * convert_factor
            amount = currency.round(amount)

            line = Line()
            line.credit = amount
            line.debit = 0
            line.account = price_line.get_account_for_billing()
            line.party = self.subscriber

            lines.append(line)
            total_amount += amount

            for tax_line in price_line.tax_lines:
                if not tax_line.tax_desc.id in taxes:
                    taxes[tax_line.tax_desc.id] = {
                        'amount': tax_line.amount * convert_factor,
                        'base': amount,
                        'object': tax_line.tax_desc,
                        'to_recalculate': tax_line.to_recalculate}
                else:
                    cur_values = taxes[tax_line.tax_desc.id]
                    cur_values['amount'] += tax_line.amount * convert_factor
                    cur_values['base'] += amount

            for fee_line in price_line.fee_lines:
                if not fee_line.fee_desc.id in fees:
                    fees[fee_line.fee_desc.id] = {
                        'amount': fee_line.amount * convert_factor,
                        'base': amount,
                        'object': fee_line.fee_desc,
                        'to_recalculate': fee_line.to_recalculate}
                else:
                    cur_values = fees[fee_line.fee_desc.id]
                    cur_values['amount'] += fee_line.amount * convert_factor
                    cur_values['base'] += amount

        for _, tax_data in taxes.iteritems():
            line_tax = Line()
            line_tax.debit = 0
            line_tax.party = self.subscriber
            line_tax.account = tax_data['object'].get_account_for_billing()
            if tax_data['to_recalculate']:
                good_version = tax_data['object'].get_version_at_date(
                    period[0])
                amount = good_version.apply_tax(tax_data['base'])
            else:
                amount = tax_data['amount']
            line_tax.credit = currency.round(amount)
            lines.append(line_tax)
            total_amount += amount

        for _, fee_data in fees.iteritems():
            line_fee = Line()
            line_fee.debit = 0
            line_fee.party = self.subscriber
            line_fee.account = fee_data['object'].get_account_for_billing()
            if fee_data['to_recalculate']:
                good_version = fee_data['object'].get_version_at_date(
                    period[0])
                amount = good_version.apply_fee(fee_data['base'])
            else:
                amount = fee_data['amount']
            line_fee.credit = currency.round(amount)
            lines.append(line_fee)
            total_amount += amount

        if payment_term:
            term_lines = payment_term.compute(total_amount, currency,
                billing_date)
        else:
            term_lines = [(Date.today(), amount)]
        for term_date, amount in term_lines:
            counterpart = Line()
            counterpart.credit = 0
            counterpart.debit = amount
            counterpart.account = self.subscriber.account_receivable
            counterpart.party = self.subscriber
            counterpart.maturity_date = term_date
            lines.append(counterpart)

        move.lines = lines
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
