import datetime
import copy

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import model, fields
from trytond.modules.coop_utils import utils, date, business
from trytond.modules.coop_utils import coop_string
from trytond.modules.insurance_product import Printable
from trytond.modules.insurance_product.product import DEF_CUR_DIG

CONTRACTSTATUSES = [
    ('', ''),
    ('quote', 'Quote'),
    ('active', 'Active'),
    ('hold', 'Hold'),
    ('terminated', 'Terminated'),
]

OPTIONSTATUS = CONTRACTSTATUSES + [
    ('refused', 'Refused'),
]

__all__ = [
    'Contract',
    'Option',
    'StatusHistory',
    'PriceLine',
    'BillingManager',
    'CoveredElement',
    'CoveredData',
    'ManagementProtocol',
    'ManagementRole',
    'Document',
    'DocumentRequest',
    'DeliveredService',
    'RequestFinder',
    'Expense',
]


class Subscribed(model.CoopView):
    'Subscribed'

    offered = fields.Many2One(
        None, 'Offered', ondelete='RESTRICT',
        states={'required': Eval('status') == 'active'})
    start_date = fields.Date('Effective Date', required=True)
    end_date = fields.Date(
        'End Date', domain=[('start_date', '<=', 'end_date')])
    # Management date is the date at which the company started to manage the
    # contract. Default value is start_date
    start_management_date = fields.Date('Management Date')
    status = fields.Selection('get_possible_status', 'Status', readonly=True)
    status_history = fields.One2Many(
        'ins_contract.status_history', 'reference', 'Status History')
    summary = fields.Function(fields.Text('Summary'), 'get_summary')
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')

    @classmethod
    def __setup__(cls):
        cls.offered = copy.copy(cls.offered)
        suffix, cls.offered.string = cls.get_offered_name()
        cls.offered.model_name = (
            '%s.%s' % (cls.get_offered_module_prefix(), suffix))
        super(Subscribed, cls).__setup__()

    @classmethod
    def get_offered_module_prefix(cls):
        return 'ins_product'

    @staticmethod
    def default_start_date():
        return utils.today()

    @classmethod
    def get_offered_name(cls):
        '''
        returns a tuple of key (without module), string for offered class name
        '''
        raise NotImplementedError

    @classmethod
    def get_possible_status(cls, name=None):
        raise NotImplementedError

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        res.add(self.start_date)
        if hasattr(self, 'end_date') and self.end_date:
            res.add(self.end_date)
        return utils.limit_dates(res, start, end)

    def init_from_offered(self, offered, start_date=None, end_date=None):
        self.offered = offered
        if start_date:
            self.start_date = max(offered.start_date, start_date)
        else:
            self.start_date = offered.start_date
        if end_date:
            self.end_date = min(offered.end_date, end_date)
        else:
            self.end_date = offered.end_date
        self.update_status('active', self.start_date)

    def get_offered(self):
        if not (hasattr(self, 'offered') and self.offered):
            return None
        return self.offered

    @staticmethod
    def get_status_transition_authorized(from_status):
        res = []
        if from_status == 'quote':
            res = ['active', 'refused']
        elif from_status == 'active':
            res = ['terminated']
        return res

    def update_status(self, to_status, at_date):
        if (hasattr(self, 'status') and not to_status in
                self.get_status_transition_authorized(self.status)):
            return False, [
                ('transition_unauthorized', (self.status, to_status))]
        if not hasattr(self, 'status_history') or not self.status_history:
            self.status_history = []
        status_history = utils.instanciate_relation(
            self.__class__, 'status_history')
        status_history.init_from_reference(self, to_status, at_date)
        self.status_history.append(status_history)
        self.status = to_status
        return True, []

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits

    @classmethod
    def get_summary(cls, instances, name):
        return dict((x.id, '') for x in instances)

    def get_currency_id(self, name):
        currency = self.get_currency()
        if currency:
            return currency.id


class Contract(model.CoopSQL, Subscribed, Printable):
    'Contract'

    __name__ = 'ins_contract.contract'
    _rec_name = 'contract_number'

    options = fields.One2Many('ins_contract.option', 'contract', 'Options')
    covered_elements = fields.One2Many(
        'ins_contract.covered_element', 'contract', 'Covered Elements')
    contract_number = fields.Char(
        'Contract Number', select=1, states={
            'required': Eval('status') == 'active'},
        depends=['status'])
    subscriber = fields.Many2One('party.party', 'Subscriber')
    # The master field is the object on which rules will be called.
    # Basically, we need an abstract way to call rules, because in some case
    # (typically in GBP rules might be managed on the group contract) the rules
    # will not be those of the product.
    master = fields.Reference(
        'Master', [
            ('', ''),
            ('ins_contract.contract', 'Contract'),
            ('ins_product.product', 'Product'),
        ])
    management = fields.One2Many(
        'ins_contract.management_role', 'contract', 'Management Roles')
    billing_manager = fields.One2Many(
        'ins_contract.billing_manager', 'contract', 'Billing Manager')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data',
        on_change=[
            'complementary_data', 'start_date', 'options', 'offered'],
        depends=[
            'complementary_data', 'start_date', 'options', 'offered'])
    # TODO replace single contact by date versionned list
    contact = fields.Many2One('party.party', 'Contact')
    documents = fields.One2Many(
        'ins_product.document_request', 'needed_by', 'Documents', size=1)

    @staticmethod
    def get_master(master):
        res = master.split(',')
        return res[0], int(res[1])

    def give_option_model(self):
        return self._fields['options'].model_name

    def get_active_options_at_date(self, at_date):
        res = []
        for elem in self.options:
            if elem.start_date <= at_date and (not hasattr(
                    elem, 'end_date') or (
                    elem.end_date is None or elem.end_date > at_date)):
                res += [elem]
        return list(set(res))

    def get_option_for_coverage_at_date(self, coverage, date):
        for elem in self.get_active_options_at_date(date):
            if elem.get_coverage() == coverage:
                return elem
        return None

    def get_active_coverages_at_date(self, at_date):
        return [
            elem.get_coverage()
            for elem in self.get_active_options_at_date(at_date)]

    def init_complementary_data(self):
        if not (hasattr(self, 'complementary_data') and
                self.complementary_data):
            self.complementary_data = {}
        self.complementary_data = self.on_change_complementary_data()[
            'complementary_data']
        return True, ()

    def get_complementary_data_value(self, at_date, value):
        return utils.get_complementary_data_value(
            self, 'complementary_data', self.get_complementary_data_def(),
            at_date, value)

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        for covered in self.covered_elements:
            res.update(covered.get_dates(start, end))
        for option in self.options:
            res.update(option.get_dates(start, end))
        return super(Contract, self).get_dates(res, start, end)

    def calculate_price_at_date(self, date):
        prices, errs = self.offered.get_result(
            'total_price',
            {
                'date': date,
                'contract': self
            })
        return (prices, errs)

    def calculate_prices_at_all_dates(self):
        prices = {}
        errs = []
        dates = self.get_dates()
        for cur_date in dates:
            price, err = self.calculate_price_at_date(cur_date)
            if price:
                prices[cur_date.isoformat()] = price
            errs += err
        return prices, errs

    def get_name_for_billing(self):
        return self.offered.name + ' - Base Price'

    def get_product(self):
        return self.offered

    def check_sub_elem_eligibility(self, at_date=None, ext=None):
        errors = []
        if not at_date:
            at_date = self.start_date
        options = dict(
            [(option.offered.code, option) for option in self.options])
        res, errs = (True, [])
        for covered_element in self.covered_elements:
            for covered_data in covered_element.covered_data:
                if (covered_data.start_date > at_date
                        or hasattr(covered_data, 'end_date') and
                        covered_data.end_date and
                        covered_data.end_date > at_date):
                    continue
                eligibility, errors = covered_data.get_coverage().get_result(
                    'sub_elem_eligibility',
                    {
                        'date': at_date,
                        'sub_elem': covered_element,
                        'data': covered_data,
                        'option': options[covered_data.get_coverage().code]
                    })
                res = res and (not eligibility or eligibility.eligible)
                if eligibility:
                    errs += eligibility.details
                errs += errors
        return (res, errs)

    @staticmethod
    def default_status():
        return 'quote'

    def get_new_contract_number(self):
        return self.get_product().get_result('new_contract_number', {})[0]

    def finalize_contract(self):
        self.contract_number = self.get_new_contract_number()
        return True, ()

    def get_rec_name(self, val):
        if self.offered and self.subscriber:
            if self.contract_number:
                return '%s (%s) - %s' % (
                    self.contract_number, self.get_product().get_rec_name(val),
                    self.subscriber.get_rec_name(val))
            else:
                return 'Contract %s - %s' % (
                    self.get_product().get_rec_name(val),
                    self.subscriber.get_rec_name(val))
        else:
            return super(Contract, self).get_rec_name(val)

    @classmethod
    def search_rec_name(cls, name, clause):
        contracts = cls.search([
            'OR',
            ('contract_number',) + clause[1:],
            ('subscriber.name',) + clause[1:],
        ])
        return [('id', 'in', [c.id for c in contracts])]

    @classmethod
    def get_summary(cls, insurers, name=None, at_date=None, lang=None):
        return ''

    @classmethod
    def get_offered_module_prefix(cls):
        return 'ins_product'

    @classmethod
    def get_offered_name(cls):
        return 'product', 'Product'

    @classmethod
    def get_possible_status(cls, name=None):
        return CONTRACTSTATUSES

    def check_at_least_one_covered(self):
        errors = []
        for covered in self.covered_elements:
            found, errors = covered.check_at_least_one_covered(errors)
            if found:
                break
        if errors:
            return False, errors
        return True, ()

    def init_covered_elements(self):
        options = dict([(o.offered.code, o) for o in self.options])
        for elem in self.covered_elements:
            CoveredData = utils.get_relation_model(elem, 'covered_data')
            if (hasattr(elem, 'covered_data') and elem.covered_data):
                existing_datas = dict([
                    (data.get_coverage().code, data)
                    for data in elem.covered_data])
            else:
                existing_datas = {}
            elem.covered_data = []
            to_delete = [data for data in existing_datas.itervalues()]
            good_datas = []
            for code, option in options.iteritems():
                if code in existing_datas:
                    existing_datas[code].init_complementary_data()
                    good_datas.append(existing_datas[code])
                    to_delete.remove(existing_datas[code])
                    continue
                else:
                    good_data = CoveredData()
                    good_data.init_from_option(option)
                    good_data.init_from_covered_element(elem)
                    good_data.status_selection = True
                    good_datas.append(good_data)
            CoveredData.delete(to_delete)
            elem.covered_data = good_datas
            elem.save()
        return True, ()

    def get_policy_owner(self, at_date=None):
        '''
        the owner of a contract could change over time, you should never use
        the direct link subscriber
        '''
        # TODO: to enhance
        return self.subscriber

    def init_options_from_covered_elements(self):
        if self.options:
            return True, ()
        self.options = []
        for coverage in self.offered.options:
            option = utils.instanciate_relation(self.__class__, 'options')
            option.init_from_offered(coverage, self.start_date)
            for covered_element in self.covered_elements:
                option.append_covered_data(covered_element)
            self.options.append(option)
        return True, ()

    def activate_contract(self):
        if not self.status == 'quote':
            return True, ()
        self.update_status('active', self.start_date)
        return True, ()

    def init_options(self):
        existing = {}
        if (hasattr(self, 'options') and self.options):
            for opt in self.options:
                existing[opt.offered.code] = opt

        good_options = []
        to_delete = [elem for elem in existing.itervalues()]

        OptionModel = Pool().get(self.give_option_model())
        for coverage in self.offered.options:
            if coverage.code in existing:
                good_opt = existing[coverage.code]
                to_delete.remove(good_opt)
            else:
                good_opt = OptionModel()
                good_opt.init_from_offered(coverage, self.start_date)
                good_opt.contract = self

            good_opt.save()
            good_options.append(good_opt)

        if to_delete:
            OptionModel.delete(to_delete)

        self.options = good_options

        return True, ()

    def get_main_contact(self):
        return self.subscriber

    def get_contact(self):
        return self.subscriber

    def get_sender(self):
        return self.get_management_role('contract_manager').protocol.party

    def get_management_role(self, role, good_date=None):
        if not good_date:
            good_date = utils.today()
        Role = Pool().get('ins_contract.management_role')
        domain = [
            utils.get_versioning_domain(good_date, do_eval=False),
            ('protocol.kind', '=', role)]
        good_roles = Role.search(domain)
        if not good_roles:
            return None
        return good_roles[0]

    def get_currency(self):
        if hasattr(self, 'offered') and self.offered:
            return self.offered.get_currency()

    def new_billing_manager(self):
        return utils.instanciate_relation(self, 'billing_manager')

    def init_billing_manager(self):
        if not (hasattr(self, 'billing_manager') and
                self.billing_manager):
            bm = self.new_billing_manager()
        self.billing_manager = [bm]

    def on_change_complementary_data(self):
        return {'complementary_data': self.offered.get_result(
            'calculated_complementary_datas',
            {'date': self.start_date, 'contract': self})[0]}


class Option(model.CoopSQL, Subscribed):
    'Subscribed Coverage'

    __name__ = 'ins_contract.option'

    contract = fields.Many2One(
        'ins_contract.contract', 'Contract', ondelete='CASCADE')
    covered_data = fields.One2Many(
        'ins_contract.covered_data', 'option', 'Covered Data')

    def get_coverage(self):
        return self.offered

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        res.update(self.offered.get_dates(dates, start, end))
        return super(Option, self).get_dates(res, start, end)

    def get_name_for_billing(self):
        return self.get_coverage().name + ' - Base Price'

    @classmethod
    def get_offered_name(cls):
        return 'coverage', 'Coverage'

    @classmethod
    def get_possible_status(cls, name=None):
        return OPTIONSTATUS

    def get_rec_name(self, name):
        if self.contract:
            res = self.contract.get_rec_name(name)
        if self.offered:
            return '%s (%s)' % (res, self.offered.get_rec_name(name))
        return super(Option, self).get_rec_name(name)

    def append_covered_data(self, covered_element=None):
        res = utils.instanciate_relation(self.__class__, 'covered_data')
        if not hasattr(self, 'covered_data'):
            self.covered_data = []
        self.covered_data.append(res)
        res.init_from_option(self)
        res.init_from_covered_element(covered_element)
        return res

    def get_contract(self):
        return self.contract

    def get_covered_data(self):
        raise NotImplementedError

    def get_coverage_amount(self):
        raise NotImplementedError

    def get_currency(self):
        if hasattr(self, 'offered') and self.offered:
            return self.offered.get_currency()


class StatusHistory(model.CoopSQL, model.CoopView):
    'Status History'

    __name__ = 'ins_contract.status_history'

    reference = fields.Reference('Reference', 'get_possible_reference')
    status = fields.Char('Status')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    @classmethod
    def get_possible_reference(cls):
        res = []
        res.append(('ins_contract.contract', 'Contract'))
        res.append(('ins_contract.option', 'Option'))
        return res

    def init_from_reference(self, reference, to_status, at_date):
        self.status = to_status
        self.start_date = at_date
        if not reference.status_history:
            return
        previous_status = reference.status_history[-1]
        if not previous_status:
            return
        previous_status.end_date = date.add_day(at_date, -1)
        if previous_status == 'active':
            reference.end_date = previous_status.end_date


class PriceLine(model.CoopSQL, model.CoopView):
    'Price Line'

    __name__ = 'ins_contract.price_line'

    amount = fields.Numeric('Amount')
    name = fields.Char('Short Description')
    master = fields.Many2One('ins_contract.price_line', 'Master Line')
    kind = fields.Selection(
        [
            ('main', 'Line'),
            ('base', 'Base'),
            ('tax', 'Tax'),
            ('fee', 'Fee')
        ], 'Kind', readonly='True')
    on_object = fields.Reference('Priced object', 'get_line_target_models')
    billing_manager = fields.Many2One(
        'ins_contract.billing_manager', 'Billing Manager')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    all_lines = fields.One2Many(
        'ins_contract.price_line', 'master', 'Lines', readonly=True)
    taxes = fields.Function(fields.Numeric('Taxes'), 'get_total_taxes')
    amount_for_display = fields.Function(
        fields.Numeric('Amount'), 'get_amount_for_display')
    start_date_calculated = fields.Function(fields.Date(
        'Start Date'), 'get_start_date')
    end_date_calculated = fields.Function(fields.Date(
        'End Date'), 'get_end_date')
    details = fields.One2ManyDomain(
        'ins_contract.price_line', 'master', 'Details', domain=[
            ('kind', '!=', 'main')], readonly=True)
    child_lines = fields.One2ManyDomain(
        'ins_contract.price_line', 'master', 'Sub-Lines', domain=[
            ('kind', '=', 'main')], readonly=True)

    def get_id(self):
        if hasattr(self, 'on_object') and self.on_object:
            return self.on_object.get_name_for_billing()
        if hasattr(self, 'name') and self.name:
            return self.name
        return self.kind

    def init_values(self):
        if not hasattr(self, 'name') or not self.name:
            self.name = ''
        self.amount = 0
        self.all_lines = []

    def init_from_result_line(self, line):
        if not line:
            return
        PLModel = Pool().get(self.__name__)
        self.init_values()
        self.amount = line.value
        for (kind, code), value in line.details.iteritems():
            detail_line = PLModel()
            detail_line.name = code
            detail_line.amount = value
            detail_line.kind = kind
            self.all_lines.append(detail_line)
        if line.desc:
            for elem in line.desc:
                child_line = PLModel()
                child_line.init_from_result_line(elem)
                self.all_lines.append(child_line)
        if not self.name:
            if line.on_object:
                self.name = utils.convert_ref_to_obj(
                    line.on_object).get_name_for_billing()
            else:
                self.name = line.name
        if line.on_object:
            self.on_object = line.on_object

    @staticmethod
    def default_kind():
        return 'main'

    def get_total_taxes(self, field_name):
        res = self.get_total_detail('tax')
        if res:
            return res

    def get_total_detail(self, name):
        res = 0
        for line in self.details:
            if line.kind == name:
                res += line.amount
        return res

    def get_amount_for_display(self, field_name):
        res = self.amount
        if not res:
            return None
        return res

    def get_start_date(self, field_name):
        if hasattr(self, 'start_date') and self.start_date:
            return self.start_date
        if self.master:
            return self.master.start_date_calculated

    def get_end_date(self, field_name):
        if hasattr(self, 'end_date') and self.end_date:
            return self.end_date
        if self.master:
            return self.master.end_date_calculated

    @classmethod
    def get_line_target_models(cls):
        f = lambda x: (x, x)
        res = [
            f(''),
            f('ins_product.product'),
            f('ins_product.coverage'),
            f('ins_contract.contract'),
            f('ins_contract.option'),
            f('ins_contract.covered_data')]
        return res

    def is_main_line(self):
        return hasattr(self, 'on_object') and self.on_object and \
            self.on_object.__name__ in (
                'ins_product.product',
                'ins_product.coverage')

    def print_line(self):
        res = [self.get_id()]
        res.append(self.name)
        res.append('%.2f' % self.amount)
        res.append(self.kind)
        res.append('%s' % self.start_date)
        res.append('%s' % self.end_date)
        if self.on_object:
            res.append(self.on_object.__name__)
        else:
            res.append('')
        return ' - '.join(res)


class BillingManager(model.CoopSQL, model.CoopView):
    'Billing Manager'
    '''
        This object will manage all billing-related content on the contract.
        It will be the target of all sql requests for automated bill
        calculation, lapsing, etc...
    '''
    __name__ = 'ins_contract.billing_manager'

    contract = fields.Many2One('ins_contract.contract', 'Contract')
    #It MUST be updated every time a billing is
    # done, so that the next batch will have up-to-date information on whether
    # or not it needs to work on this contract.
    next_billing_date = fields.Date('Next Billing Date')

    # We need a way to present our prices.
    prices = fields.One2Many(
        'ins_contract.price_line',
        'billing_manager',
        'Prices')

    def get_contract(self):
        return self.contract

    def store_prices(self, prices):
        if not prices:
            return
        PriceLine = Pool().get(self.get_price_line_model())
        to_delete = []
        if hasattr(self, 'prices') and self.prices:
            for price in self.prices:
                to_delete.append(price)
        result_prices = []
        dates = [utils.to_date(key) for key in prices.iterkeys()]
        dates.sort()
        for date, price in prices.iteritems():
            pl = PriceLine()
            pl.name = date
            details = []
            for cur_price in price:
                detail = PriceLine()
                detail.init_from_result_line(cur_price)
                details.append(detail)
            pl.all_lines = details
            pl.start_date = utils.to_date(date)
            try:
                pl.end_date = dates[dates.index(pl.start_date) + 1] + \
                    datetime.timedelta(days=-1)
            except IndexError:
                pass
            result_prices.append(pl)
        self.prices = result_prices

        self.save()

        PriceLine.delete(to_delete)

    @classmethod
    def get_price_line_model(cls):
        return cls._fields['prices'].model_name

    def get_product_frequency(self, at_date):
        res, errs = self.get_contract().offered.get_result(
            'frequency',
            {'date': at_date})
        if not errs:
            return res

    def next_billing_dates(self):
        date = max(
            Pool().get('ir.date').today(), self.get_contract().start_date)
        return (
            date,
            utils.add_frequency(self.get_product_frequency(date), date))

    def get_bill_model(self):
        return 'ins_contract.billing.bill'

    def get_prices_dates(self):
        return [elem.start_date for elem in self.prices].append(
            self.prices[-1].end_date)

    def create_price_list(self, start_date, end_date):
        dated_prices = [
            (elem.start_date, elem.end_date or end_date, elem)
            for elem in self.prices
            if (elem.start_date >= start_date and elem.start_date <= end_date)
            or (elem.end_date and elem.end_date >= start_date
                and elem.end_date <= end_date)]

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

    def lines_as_dict(self, lines):
        # lines are a list of tuples (start, end, price_line).
        # This function organizes the lines in a dict which uses the price_line
        # id (get_id) as keys
        the_dict = {}
        for elem in lines:
            id = elem[2].get_id()
            if id in the_dict:
                the_dict[id].append(elem)
            else:
                the_dict[id] = [elem]
        return the_dict

    def bill(self, start_date, end_date):
        Bill = Pool().get(self.get_bill_model())
        the_bill = Bill()
        the_bill.flat_init(start_date, end_date, self.get_contract())

        price_list = self.create_price_list(start_date, end_date)

        price_lines = self.flatten(price_list)

        the_bill.init_from_lines(price_lines)

        return the_bill


class CoveredElement(model.CoopSQL, model.CoopView):
    'Covered Element'
    '''
        Covered elements represents anything which is covered by at least one
        option of the contract.
        It has a list of covered datas which describes which options covers
        element and in which conditions.
        It could contains recursively sub covered element (fleet or population)
    '''

    __name__ = 'ins_contract.covered_element'

    contract = fields.Many2One(
        'ins_contract.contract', 'Contract', ondelete='CASCADE')
    #We need to put complementary data in depends, because the complementary
    #data are set through on_change_with and the item desc can be set on an
    #editable tree, or we can not display for the moment dictionnary in tree
    item_desc = fields.Many2One(
        'ins_product.item_desc', 'Item Desc', depends=['complementary_data'])
    covered_data = fields.One2Many(
        'ins_contract.covered_data', 'covered_element', 'Covered Element Data')
    name = fields.Char('Name')
    parent = fields.Many2One('ins_contract.covered_element', 'Parent')
    sub_covered_elements = fields.One2Many(
        'ins_contract.covered_element', 'parent', 'Sub Covered Elements')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data',
        on_change_with=['item_desc', 'complementary_data'])
    complementary_data_summary = fields.Function(
        fields.Char('Complementary Data', on_change_with=['item_desc']),
        'on_change_with_complementary_data_summary')

    def get_name_for_billing(self):
        return self.name

    def get_name_for_info(self):
        return self.name

    def get_rec_name(self, value):
        res = super(CoveredElement, self).get_rec_name(value)
        if self.item_desc:
            res = coop_string.concat_strings(
                self.item_desc.get_rec_name(value), res)
            if self.name:
                res = '%s : %s' % (res, self.name)
        elif self.name:
            res = coop_string.concat_strings(res, self.name)
        return res

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        for data in self.covered_data:
            res.update(data.get_dates(dates, start, end))
        if hasattr(self, 'sub_covered_elements'):
            for sub_elem in self.sub_covered_elements:
                res.update(sub_elem.get_dates(dates, start, end))
        return res

    def check_at_least_one_covered(self, errors=None):
        if not errors:
            errors = []
        found = False
        for data in self.covered_data:
            if data.status == 'active':
                found = True
                break
        if not found:
            errors.append(('need_option', (self.get_rec_name(''))))
        if errors:
            return False, errors
        return True, ()

    def on_change_with_complementary_data(self):
        if self.complementary_data:
            return self.complementary_data
        elif self.item_desc:
            return utils.init_complementary_data(
                self.item_desc.complementary_data_def)

    def on_change_with_complementary_data_summary(self, name=None):
        return ' '.join([
            '%s: %s' % (x[0], x[1])
            for x in self.complementary_data.iteritems()])


class CoveredData(model.CoopSQL, model.CoopView):
    'Covered Data'

    __name__ = 'ins_contract.covered_data'

    option = fields.Many2One('ins_contract.option', 'Subscribed Coverage')
    coverage = fields.Many2One(
        'ins_product.coverage', 'Coverage', ondelete='RESTRICT')
    covered_element = fields.Many2One(
        'ins_contract.covered_element', 'Covered Element', ondelete='CASCADE')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data', on_change=[
            'complementary_data', 'option', 'start_date'],
        depends=['complementary_data', 'option', 'start_date'])
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    status = fields.Selection(OPTIONSTATUS, 'Status')

    @classmethod
    def default_status(cls):
        return 'active'

    def get_name_for_billing(self):
        return self.covered_element.get_name_for_billing()

    def init_complementary_data(self):
        if not (hasattr(self, 'complementary_data') and
                self.complementary_data):
            self.complementary_data = {}
        self.complementary_data = self.on_change_complementary_data()[
            'complementary_data']

    def init_from_option(self, option):
        self.option = option
        self.coverage = option.offered
        self.start_date = option.start_date
        self.end_date = option.end_date
        self.init_complementary_data()

    def on_change_complementary_data(self):
        return {'complementary_data': self.option.contract.offered.get_result(
            'calculated_complementary_datas', {
                'date': self.start_date,
                'contract': self.option.contract,
                'sub_elem': self})[0]}

    def init_from_covered_element(self, covered_element):
        #self.covered_element = covered_element
        pass

    def get_dates(self, dates=None, start=None, end=None):
        if dates:
            res = set(dates)
        else:
            res = set()
        res.add(self.start_date)
        if hasattr(self, 'end_date') and self.end_date:
            res.add(self.end_date)
        return utils.limit_dates(res, start, end)

    def get_coverage(self):
        if (hasattr(self, 'coverage') and self.coverage):
            return self.coverage
        if (hasattr(self, 'option') and self.option):
            return self.option.offered


class ManagementProtocol(model.CoopSQL, model.CoopView):
    'Management Protocol'

    __name__ = 'ins_contract.management_protocol'

    kind = fields.Selection(
        [
            ('provider', 'Business Provider'),
            ('claim_manager', 'Claim Manager'),
            ('contract_manager', 'Contract Manager'),
        ],
        'Kind',
        required=True,
    )
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    party = fields.Many2One('party.party', 'Party')

    def get_rec_name(self, name):
        return self.party.get_rec_name(name)


class ManagementRole(model.CoopSQL, model.CoopView):
    'Management Role'

    __name__ = 'ins_contract.management_role'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    protocol = fields.Many2One(
        'ins_contract.management_protocol', 'Protocol', required=True,
        domain=[utils.get_versioning_domain('start_date', 'end_date')],
        depends=['start_date', 'end_date'],
        ondelete='RESTRICT',)
    contract = fields.Many2One(
        'ins_contract.contract', 'Contract', ondelete='CASCADE')
    kind = fields.Function(
        fields.Char(
            'Kind',
            on_change_with=['protocol'],
            depends=['protocol'],
        ),
        'on_change_with_kind',
    )

    def on_change_with_kind(self, name=None):
        if not (hasattr(self, 'protocol') and self.protocol):
            return ''
        return coop_string.translate_value(self.protocol, 'kind')


class DeliveredService(model.CoopSQL, model.CoopView):
    'Delivered Service'

    __name__ = 'ins_contract.delivered_service'

    subscribed_service = fields.Many2One(
        'ins_contract.option', 'Coverage', ondelete='RESTRICT')
    expenses = fields.One2Many(
        'ins_contract.expense', 'delivered_service', 'Expenses')

    def get_rec_name(self, name=None):
        if self.subscribed_service:
            return self.subscribed_service.get_rec_name(name)
        return super(DeliveredService, self).get_rec_name(name)

    def get_expense(self, code):
        for expense in self.expenses:
            if expense.kind and expense.kind.code == code:
                return expense.amount, expense.currency

    def get_total_expense(self):
        res = [0, None]
        for expense in self.expenses:
            if not res[1]:
                res[1] = expense.currency
            if res[1] == expense.currency:
                res[0] += expense.amount
        return res


class Expense(model.CoopSQL, model.CoopView):
    'Expense'

    __name__ = 'ins_contract.expense'

    delivered_service = fields.Many2One(
        'ins_contract.delivered_service', 'Delivered Service',
        ondelete='CASCADE')
    kind = fields.Many2One('ins_product.expense_kind', 'Kind')
    amount = fields.Numeric(
        'Amount', required=True,
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Function(
        fields.Integer('Currency Digits', states={'invisible': True}),
        'get_currency_digits')

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def get_currency_digits(self, name):
        if hasattr(self, 'currency') and self.currency:
            return self.currency.digits


class DocumentRequest():
    'Document Request'

    __name__ = 'ins_product.document_request'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by = copy.copy(cls.needed_by)
        cls.needed_by.selection.append(
            ('ins_contract.contract', 'Contract'))


class Document():
    'Document'

    __name__ = 'ins_product.document'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        cls.for_object = copy.copy(cls.for_object)
        cls.for_object.selection.append(
            ('ins_contract.contract', 'Contract'))
        cls.for_object.selection.append(
            ('ins_contract.option', 'Option'))
        cls.for_object.selection.append(
            ('ins_contract.covered_element', 'Covered Element'))


class RequestFinder():
    'Request Finder'

    __name__ = 'ins_product.request_finder'
    __metaclass__ = PoolMeta

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({
            'ins_contract.contract': (
                'Contract', 'contract_number')})
        return result
