import datetime

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.pyson import Eval, If

from trytond.modules.coop_utils import model, fields, utils, date, abstract
from trytond.modules.coop_utils import export
from trytond.modules.insurance_product import product
from trytond.modules.insurance_contract.contract import IS_PARTY

__all__ = [
    'PaymentMethod',
    'PriceLine',
    'BillingManager',
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
    'TaxVersion',
    'FeeVersion',
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


class PriceLine(model.CoopSQL, model.CoopView):
    'Price Line'

    __name__ = 'billing.price_line'

    amount = fields.Numeric('Amount')
    name = fields.Function(fields.Char('Short Description'), 'get_short_name')
    master = fields.Many2One('billing.price_line', 'Master Line')
    kind = fields.Selection(
        [
            ('main', 'Line'),
            ('base', 'Base'),
            ('tax', 'Tax'),
            ('fee', 'Fee')
        ], 'Kind', readonly='True')
    on_object = fields.Reference('Priced object', 'get_line_target_models')
    contract = fields.Many2One('contract.contract', 'Contract')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    all_lines = fields.One2Many('billing.price_line', 'master', 'Lines',
        readonly=True, loading='lazy')
    amount_for_display = fields.Function(
        fields.Numeric('Amount'), 'get_amount_for_display')

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
            return None
        return target

    def calculate_my_kind(self, line):
        test_value = line.on_object.__name__
        if test_value == 'ins_product.pricing_component':
            return line.on_object.kind
        else:
            return 'main'

    def init_from_result_line(self, line):
        if not line:
            return
        PriceLineModel = Pool().get(self.__name__)
        self.init_values()
        self.amount = line.amount
        self.on_object = self.get_good_on_object(line)
        self.start_date = line.start_date if hasattr(
            line, 'start_date') else None
        self.frequency = line.frequency if hasattr(line, 'frequency') else ''
        self.contract = line.contract if hasattr(line, 'contract') else None
        self.kind = self.calculate_my_kind(line)
        for detail in line.details:
            detail_line = PriceLineModel()
            detail_line.init_from_result_line(detail)
            self.all_lines.append(detail_line)

    def get_amount_for_display(self, field_name):
        res = self.amount
        if not res:
            return None
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

    def is_main_line(self):
        return self.contract is not None


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

    def on_change_with_payment_mode(self, name=None):
        if not (hasattr(self, 'payment_method') and self.payment_method):
            return ''
        return self.payment_method.payment_mode

    def create_price_list(self, start_date, end_date):
        dated_prices = [
            (elem.start_date, elem.end_date or end_date, elem)
            for elem in self.contract.prices
            if (
                (elem.start_date >= start_date and elem.start_date <= end_date)
                or (
                    elem.end_date and elem.end_date >= start_date
                    and elem.end_date <= end_date))]
        return dated_prices

    def flatten(self, prices):
        # prices is a list of tuples (start, end, price_line).
        # aggregate returns one price_line which aggregates all of the
        # provided price_lines, in which all lines have set start and end dates
        lines_desc = []
        for elem in prices:
            if elem[2].is_main_line():
                if elem[2].amount:
                    lines_desc.append(elem)
            else:
                lines_desc += self.flatten(
                    [(elem[0], elem[1], line) for line in elem[2].child_lines])
        return lines_desc

    def bill(self, start_date, end_date):
        Bill = Pool().get(self.get_bill_model())
        the_bill = Bill()
        the_bill.flat_init(start_date, end_date, self.contract)
        price_list = self.create_price_list(start_date, end_date)
        price_lines = self.flatten(price_list)
        the_bill.init_from_lines(price_lines)
        return the_bill


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

    bills = fields.One2Many(
        'billing.billing.bill', None, 'Bill', states={'readonly': True})


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
        bill_dates = contract.billing_managers[0].next_billing_dates()
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
        billing_manager = contract.billing_managers[0]
        start_date = self.bill_parameters.start_date
        end_date = self.bill_parameters.end_date
        the_bill = billing_manager.bill(start_date, end_date)
        the_bill.contract = None
        the_bill.save()
        return {'bills': [the_bill.id]}

    def transition_cancel_bill(self):
        Bill = Pool().get('billing.billing.bill')
        the_bill = self.bill_display.bills[0]
        Bill.delete([the_bill])
        return 'end'

    def transition_accept_bill(self):
        the_bill = self.bill_display.bills[0]
        the_bill.contract = self.bill_parameters.contract
        the_bill.save()
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

    def get_name_for_billing(self):
        return self.offered.name + ' - Base Price'

    def new_billing_manager(self):
        return utils.instanciate_relation(self, 'billing_managers')

    def init_billing_manager(self):
        if not (hasattr(self, 'billing_managers') and
                self.billing_managers):
            bm = self.new_billing_manager()
            bm.contract = self
            bm.start_date = self.start_date
            bm.payment_method = self.offered.get_default_payment_method()
            self.billing_managers = [bm]
            bm.save()

    def next_billing_dates(self):
        start_date = self.next_billing_date
        return (
            start_date,
            utils.add_frequency(
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
        print utils.format_data(prices)
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
            try:
                price_line.end_date = dates[dates.index(price_line.start_date)
                    + 1] + datetime.timedelta(days=-1)
            except IndexError:
                pass
            result_prices.append(price_line)
        self.prices = result_prices
        self.save()

        PriceLine.delete(to_delete)


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


class TaxVersion():
    'Tax Version'

    __metaclass__ = PoolMeta
    __name__ = 'coop_account.tax_version'

    apply_at_pricing_time = fields.Boolean('Apply when Pricing')


class FeeVersion():
    'Fee Version'

    __metaclass__ = PoolMeta
    __name__ = 'coop_account.fee_version'

    apply_at_pricing_time = fields.Boolean('Apply when Pricing')
