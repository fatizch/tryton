import datetime

# Needed for storing and displaying objects
from trytond.model import fields as fields

from trytond.modules.coop_utils import model as model
from trytond.modules.coop_utils import utils as utils

# Needed for getting models
from trytond.pool import Pool

__all__ = [
    'GenericExtension',
    'GenericContract',
    'Contract',
    'Option',
    'PriceLine',
    'BillingManager',
    'CoveredElement',
    'CoveredData',
    'BrokerManager',
    ]

CONTRACTSTATUSES = [
    ('quote', 'Quote'),
    ('active', 'Active'),
    ('hold', 'Hold'),
    ('terminated', 'Terminated'),
    ]

OPTIONSTATUS = [
    ('Active', 'Active'),
    ('Refused', 'Refused')
    ]


class GenericExtension(model.CoopView):
    '''
        This class is the mother class of all product-specific extensions.
        Extension classes will be defined in the proper module
        (ex: life_contract) and must inherit from GenericExtension.

        GenericExtension provides the covered_elements list, which contains
        a list of covered elements whose model depends on the associated
        product.

        In sub-classes, it is necessary to override __setup__ to change
        the model_name attribute of the 'covered_elements' field.
    '''

    __name__ = 'ins_contract.generic_extension'

    covered_elements = fields.One2Many('ins_contract.covered_element',
                                       'extension',
                                       'Coverages')

    contract = fields.Many2One(
        'ins_contract.contract',
        'The contract',
        ondelete='CASCADE')

    def get_dates(self):
        res = set()
        for covered in self.covered_elements:
            for data in covered.covered_data:
                res.add(data.start_date)
                if hasattr(data, 'end_date') and data.end_date:
                    res.add(data.end_date)
        return res

    def get_extension_name(self):
        return ''


class GenericContract(model.CoopSQL, model.CoopView):
    '''
        This class will provide the basics of all contracts :
            Contract Number
            Subscriber
            Start_Date
            Status
            Management_Date
            BillingManager
            BrokerManager
    '''

    # Effective date is the date at which the contract "starts" :
    #    The client pays its premium
    #    Claims can be declared
    start_date = fields.Date('Effective Date',
                                 required=True)

    # Management date is the date at which the company started to manage the
    # contract. Default value is start_date
    start_management_date = fields.Date('Management Date')

    # Contract Number will be the number which will be used to reference the
    # contract for external uses (forms, other softwares...)
    contract_number = fields.Char('Contract Number',
                                  # required=True,
                                  select=1)

    # The subscriber is the client which did (or will) sign the contract.
    # It is an important part of the contract life, as he usually is the
    # recipient of the letters of the contract, he will pay the premium etc...
    #
    # Some business rules might need some of the subscriber's data to compute.
    subscriber = fields.Many2One('party.party',
                                 'Subscriber',
                                 select='0')

    # Status represents the contract state at current time.
    status = fields.Selection(CONTRACTSTATUSES,
                              'Status',
                              readonly=True)

    # The broker manager will be used to describe the relation between the
    # contract and its broker (if it exists)
    broker_manager = fields.Many2One('ins_contract.broker_manager',
                                     'Broker Manager')

    # The billing manager will be in charge of all billing-related actions.
    # The select statements for billing will use this object to get the list
    # of tasks
    billing_manager = fields.One2Many('ins_contract.billing_manager',
                                      'contract',
                                      'Billing Manager')

    # This field will be used to compute a textuel synthesis of the contract
    # that will be displayed on top of the contract forms
    summary = fields.Function(fields.Text('Summary'), 'get_summary')

    def get_new_contract_number(self):
        raise NotImplementedError

    def get_manager_model(self):
        return 'ins_contract.billing_manager'

    def get_product(self):
        pass

    def finalize_contract(self):
        raise NotImplementedError


class Contract(GenericContract):
    'Contract'
    '''
    This class represents the contract, and will be at the center of
    many business processes.
    '''
    __name__ = 'ins_contract.contract'

    # The option list is very important, as it is what really "makes" the
    # contract. Almost all the main actions on the contract will use either
    # one or all options. If you want to generate an invoice, you need the
    # options.
    #
    # If you want to pay for a claim, you got to check the options to know
    # whether you got to do so or not, and if you do how much you will pay
    options = fields.One2Many('ins_contract.option',
                              'contract',
                              'Options')

    # Each contract will be build from an offered product, which will give
    # access to a number of business rules. Those rules will be used all
    # along the contract's life, so we need to easily get access to them,
    # through a direct link to the product.
    product = fields.Many2One('ins_product.product',
                              'Product',
                              required=True)

    # On the other hand, the Product Extension will represents all product
    # specific data, including coverages description. It will be one major
    # element used in most of the product specific business rules.
    product_extension = fields.Reference('Product Extension',
                                         'get_extension_models')

    # The master field is the object on which rules will be called.
    # Basically, we need an abstract way to call rules, because in some case
    # (typically in GBP rules might be managed on the group contract) the rules
    # will not be those of the product.
    master = fields.Reference('Master',
                              [('ins_contract.contract', 'Contract'),
                               ('ins_product.product', 'Product')])

    # This field will be used to store the answer to dynamic questions asked
    # at subscription time to the subscriber depending on the product he chose.
    dynamic_data = fields.Dict(
        'Dynamic Data',
        schema_model='ins_product.schema_element')

    @staticmethod
    def get_master(master):
        res = master.split(',')
        return res[0], int(res[1])

    @staticmethod
    def get_extension_models():
        return [(model__name__, model.get_extension__name__())
                for (model__name__, model) in Pool().iterobject()
                if hasattr(model, 'get_extension__name__')
                    and model.get_extension__name__() != '']

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
        return [elem.get_coverage()
            for elem in self.get_active_options_at_date(at_date)]

    def get_active_extensions(self):
        for elem in dir(self):
            if hasattr(self, elem) and elem.startswith('extension_'):
                attr = getattr(self, elem)
                if attr:
                    yield attr[0]

    def get_extensions_dates(self):
        res = set()
        for ext in self.get_active_extensions():
            res.update(ext.get_dates())
        return res

    def get_dynamic_data_value(self, at_date, value):
        if not(hasattr(self, 'dynamic_data') and self.dynamic_data):
            return None
        try:
            return self.dynamic_data[value]
        except KeyError:
            return None

    def get_dates(self, start=None, end=None):
        res = set()
        res.add(self.start_date)
        res.update(self.get_extensions_dates())
        for cur_option in self.options:
            res.update(cur_option.get_dates())
        return utils.limit_dates(res, start, end)

    def calculate_price_at_date(self, date):
        prices, errs = self.product.get_result(
            'total_price',
            {'date': date,
            'contract': self})
        return (prices, errs)

    def calculate_prices_at_all_dates(self):
        prices = {}
        errs = []
        dates = self.get_dates()
        for cur_date in dates:
            price, err = self.calculate_price_at_date(cur_date)
            prices[cur_date.isoformat()] = price
            errs += err
        return prices, errs

    def get_name_for_billing(self):
        return self.product.name + ' - Base Price'

    def get_product(self):
        return self.product

    def check_sub_elem_eligibility(self, at_date, ext):
        options = dict([
            (option.coverage.code, option)
            for option in self.options
            ])
        res, errs = (True, [])
        for covered_element in getattr(self, ext)[0].covered_elements:
            for covered_data in covered_element.covered_data:
                if (covered_data.start_date > at_date
                        or hasattr(covered_data, 'end_date') and
                        covered_data.end_date and
                        covered_data.end_date > at_date):
                    continue
                eligibility, errors = covered_data.for_coverage.get_result(
                    'sub_elem_eligibility',
                    {'date': at_date,
                    'sub_elem': covered_element,
                    'data': covered_data,
                    'option': options[covered_data.for_coverage.code]})
                res = res and eligibility.eligible
                errs += eligibility.details
                errs += errors
        return (res, errs)

    def default_status(self):
        return 'quote'

    def get_new_contract_number(self):
        return self.get_product().get_result(
            'new_contract_number', {})[0]

    def finalize_contract(self):
        self.contract_number = self.get_new_contract_number()

    def get_rec_name(self, val):
        return '%s (%s) - %s' % (
            self.contract_number, self.get_product().get_rec_name(val),
            self.subscriber.get_rec_name(val))

    @classmethod
    def search_rec_name(cls, name, clause):
        contracts = cls.search([
                'OR',
                ('contract_number',) + clause[1:],
                ('subscriber.name',) + clause[1:],
            ])
        return [('id', 'in', [c.id for c in contracts])]


class Option(model.CoopSQL, model.CoopView):
    '''
    This class is an option, that is a global coverage which will be applied
    to all covered persons on the contract.

    An instance is based on a product.coverage, which is then customized at
    subscription time in order to let the client decide precisely what
    he wants.

    Typically, on a life contract, the product.coverage might allow a choice
    of coverage amount. The Option will store the choice of the client at
    subscription time, so that it can be used later when calculating premium
    or benefit.
    '''
    __name__ = 'ins_contract.option'

    # Every option is linked to a contract (and only one !)
    # Also, if the contract is destroyed, so should the option
    contract = fields.Many2One('ins_contract.contract',
                               'Contract',
                               ondelete='CASCADE')

    # The option is build from a model, the product.coverage, and then
    # customized depending on the client's desiderata. But the offered
    # coverage provides all the business rules for the option life :
    # premium calculation rules, benefit rules eligibility rules, etc...
    # Almost all actions performed on an option will require a call to a
    # business rule of the offered coverage
    coverage = fields.Many2One('ins_product.coverage',
                               'Offered Coverage',
                               required=True)

    # Effective date is the date at which the option "starts" to be effective :
    #    The client pays its premium for it
    #    Claims can be declared and benefits paid on the coverage
    start_date = fields.Date('Effective Date', required=True)

    # To go with it, there is the end_date wich marks the end of coverage :
    end_date = fields.Date('Effective_date',
                           domain=[('start_date', '<=', 'end_date')])

    option_data = fields.Reference('Option Data',
                                   'get_data_model')

    @staticmethod
    def get_data_model():
        return [(model__name__, model.get_option_data_name())
                for (model__name__, model) in Pool().iterobject()
                if hasattr(model, 'get_option_data_name')
                    and model.get_option_data_name() != '']

    def get_coverage(self):
        return self.coverage

    def get_dates(self):
        res = set()
        res.add(self.start_date)
        if hasattr(self, 'end_date') and self.end_date:
            res.add(self.end_date)
        res.update(self.coverage.get_dates())
        return res

    def get_name_for_billing(self):
        return self.get_coverage().name + ' - Base Price'


class PriceLine(model.CoopSQL, model.CoopView):
    'Price Line'
    # We need an object to present pricing line, even though it is just for
    # dsplaying.
    __name__ = 'ins_contract.price_line'

    # First are the 'real' fields :

    amount = fields.Numeric('Amount')

    name = fields.Char('Short Description')

    master = fields.Many2One(
        'ins_contract.price_line',
        'Master Line')

    kind = fields.Selection(
        [('main', 'Line'),
        ('base', 'Base'),
        ('tax', 'Tax'),
        ('fee', 'Fee')],
        'Kind',
        readonly='True')

    on_object = fields.Reference(
        'Priced object',
        'get_line_target_models')

    billing_manager = fields.Many2One(
        'ins_contract.billing_manager',
        'Billing Manager')

    start_date = fields.Date('Start Date')

    end_date = fields.Date('End Date')

    all_lines = fields.One2Many(
        'ins_contract.price_line',
        'master',
        'Lines',
        readonly=True)

    # Now some display fields :

    taxes = fields.Function(fields.Numeric('Taxes'), 'get_total_taxes')

    amount_for_display = fields.Function(
        fields.Numeric('Amount'), 'get_amount_for_display')

    start_date_calculated = fields.Function(fields.Date(
        'Start Date'), 'get_start_date')

    end_date_calculated = fields.Function(fields.Date(
        'End Date'), 'get_end_date')

    # Two special fields : they use the all_lines One2Many field as a base
    # for two Domain-Dependant One2Many :

    details = model.One2ManyDomain(
        'ins_contract.price_line',
        'master',
        'Details',
        domain=[('kind', '!=', 'main')],
        readonly=True)

    child_lines = model.One2ManyDomain(
        'ins_contract.price_line',
        'master',
        'Sub-Lines',
        domain=[('kind', '=', 'main')],
        readonly=True)

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

    @staticmethod
    def get_line_target_models():
        f = lambda x: (x, x)
        res = [
            f('ins_product.product'),
            f('ins_product.coverage'),
            f('ins_contract.contract'),
            f('ins_contract.option')]
        res += utils.get_descendents('ins_contract.covered_data')
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
    '''
        This object will manage all billing-related content on the contract.
        It will be the target of all sql requests for automated bill
        calculation, lapsing, etc...
    '''
    __name__ = 'ins_contract.billing_manager'

    # This is the related contract for which the current billing manager is
    # defined. It is necessary to have this link as the billing manager is just
    # an interface for billing-related actions, the critical are stored on the
    # contract.
    contract = fields.Many2One('ins_contract.contract',
                               'Contract')

    # This is a critical field. It MUST be updated every time a billing is
    # done, so that the next batch will have up-to-date information on whether
    # or not it needs to work on this contract.
    next_billing_date = fields.Date('Next Billing Date')

    # We need a way to present our prices.
    prices = fields.One2Many(
        'ins_contract.price_line',
        'billing_manager',
        'Prices')

    def store_prices(self, prices):
        if not prices:
            return
        if hasattr(self, 'prices') and self.prices:
            Pool().get(self._fields['prices'].model_name).delete(self.prices)
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

    def get_product_frequency(self, at_date):
        res, errs = self.contract.product.get_result(
            'frequency',
            {'date': at_date})
        if not errs:
            return res

    def next_billing_dates(self):
        date = max(Pool().get('ir.date').today(), self.contract.start_date)
        return (
            date,
            utils.add_frequency(self.get_product_frequency(date), date))

    def get_bill_model(self):
        return 'ins_contract.billing.bill'

    def get_prices_dates(self):
        return [elem.start_date
            for elem in self.prices].append(self.prices[-1].end_date)

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
        the_bill.flat_init(start_date, end_date, self.contract)

        price_list = self.create_price_list(start_date, end_date)

        price_lines = self.flatten(price_list)

        the_bill.init_from_lines(price_lines)

        return the_bill


class CoveredElement(model.CoopView):
    'Covered Element'
    '''
        Covered elements represents anything which is covered by at least one
        option of the contract.

        It got a link with a dependant element, which is product dependant. It
        also has a list of covered datas which describes which options covers
        element and in which conditions.
    '''

    __name__ = 'ins_contract.covered_element'

    covered_data = fields.One2Many('ins_contract.covered_data',
                                   'for_covered',
                                   'Coverage Data')

    extension = fields.Many2One(
        'ins_contract.generic_extension',
        'Extension',
        ondelete='CASCADE')

    def get_name_for_billing(self):
        pass

    def get_name_for_info(self):
        pass

    def get_rec_name(self, value):
        return ''


class CoveredData(model.CoopView):
    'Coverage Data'
    '''
        Covered Datas are the link between covered elements and options.

        Basically, it is the start and end date of covering.
    '''
    __name__ = 'ins_contract.covered_data'

    for_coverage = fields.Many2One(
        'ins_product.coverage',
        'Coverage',
        ondelete='CASCADE')

    for_covered = fields.Many2One(
        'ins_contract.covered_element',
        'Covered Element',
        ondelete='CASCADE')

    start_date = fields.Date('Start Date')

    end_date = fields.Date('End Date')

    def get_name_for_billing(self):
        return self.for_covered.get_name_for_billing()


class BrokerManager(model.CoopSQL, model.CoopView):
    '''
        This entity will be used to manage the relation between the contract
        and its broker
    '''
    __name__ = 'ins_contract.broker_manager'
    broker = fields.Many2One('party.party',
                             'Broker')
