# Needed for storing and displaying objects
from trytond.model import fields as fields

from trytond.modules.coop_utils import CoopView, CoopSQL, convert_ref_to_obj
from trytond.modules.coop_utils import limit_dates, to_date

# Needed for getting models
from trytond.pool import Pool

import datetime

from trytond.modules.insurance_product import Coverage

__all__ = [
    'SubscriptionManager',
    'GenericContract',
    'Contract',
    'Option',
    'BillingManager',
    'CoveredElement',
    'CoveredData',
    'ExtensionLife',
    'ExtensionCar',
    'CoveredPerson',
    'CoveredCar',
    'BrokerManager',
    'PriceLine'
    ]

CONTRACTNUMBER_MAX_LENGTH = 10
CONTRACTSTATUSES = [
    ('Quote', 'Quote'),
    ('Active', 'Active'),
    ('Hold', 'Hold'),
    ('Terminated', 'Terminated'),
    ]
OPTIONSTATUS = [
    ('Active', 'Active'),
    ('Refused', 'Refused')
    ]


class SubscriptionManager(CoopSQL, CoopView):
    '''
        The subscription Manager will be used to store subscription-only
        related data.
    '''
    __name__ = 'ins_contract.subs_manager'


class GenericExtension(CoopSQL, CoopView):
    '''
    Here comes the Extension which will contains all data needed by a specific
    product to compute rates, benefits etc.

    It should includes all coverage data, whether we are dealing with life
    insurance or PnC, each one of those is just a bunch of data that will be
    used in the business rules to calculate stuff.
    '''
    covered_elements = fields.One2Many('ins_contract.covered_element',
                                       'extension',
                                       'Coverages')

    def get_dates(self):
        res = set()
        for covered in self.covered_elements:
            for data in covered.covered_data:
                res.add(data.start_date)
                if hasattr(data, 'end_date') and data.end_date:
                    res.add(data.end_date)
        return res


class GenericContract(CoopSQL, CoopView):
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
                                  select=1,
                                  size=CONTRACTNUMBER_MAX_LENGTH)

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

    @staticmethod
    def get_new_contract_number():
        return 'Ct00000001'

    def get_manager_model(self):
        return 'ins_contract.billing_manager'


class Contract(GenericContract):
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

    extension_life = fields.Many2One('ins_contract.extension_life',
                                     'Life Extension')

    extension_car = fields.Many2One('ins_contract.extension_car',
                                    'Car Extension')

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

    def get_dates(self, start=None, end=None):
        res = set()
        res.add(self.start_date)
        res.update(self.extension_life.get_dates())
        for cur_option in self.options:
            res.update(cur_option.get_dates())
        return limit_dates(res, start, end)

    def calculate_price_at_date(self, date):
        price, errs = self.product.get_result(
            'total_price',
            {'date': date,
            'contract': self})
        return (price, errs)

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


class Option(CoopSQL, CoopView):
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


class PriceLine(CoopSQL, CoopView):
    'Price Line'
    # We need an object to present pricing line, even though it is just for
    # dsplaying.
    __name__ = 'ins_contract.price_line'

    amount = fields.Numeric('Amount')

    name = fields.Char('Short Description')

    on_object = fields.Reference(
        'Priced object',
        'get_line_target_models')

    child_lines = fields.One2Many(
        'ins_contract.price_line',
        'master',
        'Sub-Lines')

    billing_manager = fields.Many2One(
        'ins_contract.billing_manager',
        'Billing Manager')

    master = fields.Many2One(
        'ins_contract.price_line',
        'Master Line')

    start_date = fields.Date('Start Date')

    end_date = fields.Date('End Date')

    def get_id(self):
        if hasattr(self, 'on_object') and self.on_object:
            return self.on_object.get_name_for_billing()
        return self.name

    def init_values(self):
        if not hasattr(self, 'name') or not self.name:
            self.name = ''
        self.amount = 0
        self.child_lines = []

    def init_from_result_line(self, line):
        if not line:
            return
        self.init_values()
        self.amount = line.value
        if not self.name:
            if line.on_object:
                self.name = convert_ref_to_obj(
                    line.on_object).get_name_for_billing()
            else:
                self.name = line.name
        if line.on_object:
            self.on_object = line.on_object
        if line.desc:
            self.child_lines = []
            Model = Pool().get(self.__name__)
            for elem in line.desc:
                child_line = Model()
                child_line.init_from_result_line(elem)
                self.child_lines.append(child_line)

    @staticmethod
    def get_line_target_models():
        f = lambda x: (x, x)
        return [
            f('ins_contract.contract'),
            f('ins_contract.option'),
            f('ins_contract.covered_data')]


class BillingManager(CoopSQL, CoopView):
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
        dates = [to_date(key) for key in prices.iterkeys()]
        dates.sort()
        for date, price in prices.iteritems():
            pl = PriceLine()
            pl.name = date
            details = PriceLine()
            details.init_from_result_line(price)
            pl.child_lines = [details]
            pl.start_date = to_date(date)
            try:
                pl.end_date = dates[dates.index(pl.start_date) + 1] + \
                    datetime.timedelta(days=-1)
            except IndexError:
                pass
            result_prices.append(pl)
        self.prices = result_prices

    def next_billing_dates(self):
        return (
            datetime.date.today(),
            datetime.date.today() + datetime.timedelta(days=90))

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
            if not hasattr(elem[2], 'child_lines') or not elem[2].child_lines:
                if elem[2].amount:
                    lines_desc.append(elem)
                continue
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


class CoveredElement(CoopSQL, CoopView):
    'Covered Element'
    '''
        Covered elements represents anything which is covered by at least one
        option of the contract.

        It got a link with a dependant element, which is product dependant. It
        also has a list of covered datas which describes which options covers
        element and in which conditions.
    '''
    __name__ = 'ins_contract.covered_element'
    product_specific = fields.Reference('Specific Part',
                                        'get_specific_models')

    covered_data = fields.One2Many('ins_contract.covered_data',
                                   'for_covered',
                                   'Coverage Data')

    extension = fields.Reference('Extension',
                                 'get_extension_models')

    @staticmethod
    def get_specific_models():
        return [(model__name__, model.get_specific_model_name())
                for (model__name__, model) in Pool().iterobject()
                if hasattr(model, 'get_specific_model_name')
                    and model.get_specific_model_name() != '']

    @staticmethod
    def get_extension_models():
        res = [(elem.__name__, elem.__name__) for elem in
               GenericExtension.__subclasses__()]
        return res

    def get_name_for_billing(self):
        return convert_ref_to_obj(self.product_specific).get_name_for_billing()


class CoveredData(CoopSQL, CoopView):
    '''
        Covered Datas are the link between covered elements and options.

        Basically, it is the start and end date of covering.
    '''
    __name__ = 'ins_contract.covered_data'
    for_covered = fields.Reference(
        'Covered Element',
        'get_covered_element_models')
    for_coverage = fields.Reference(
        'Coverage',
        'get_coverages_models')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    @staticmethod
    def get_covered_element_models():
        res = [(elem.__name__, elem.__name__) for elem in
               CoveredElement.__subclasses__()]
        res.append((lambda x: (x, x))(CoveredElement.__name__))
        return res

    @staticmethod
    def get_coverages_models():
        res = [(elem.__name__, elem.__name__) for elem in
               Coverage.__subclasses__()]
        res.append((lambda x: (x, x))(Coverage.__name__))
        return res

    def get_name_for_billing(self):
        return convert_ref_to_obj(self.for_covered).get_name_for_billing()


class ExtensionLife(GenericExtension):
    '''
        This is a particular case of contract extension designed for Life
        insurance products.
    '''
    __name__ = 'ins_contract.extension_life'

    @staticmethod
    def get_covered_element_model():
        return 'ins_contract.covered_person'


class ExtensionCar(GenericExtension):
    '''
        This is a particular case of contract extension designed for Car
        insurance products.
    '''
    __name__ = 'ins_contract.extension_car'

    @staticmethod
    def get_covered_element_model():
        return 'ins_contract.covered_car'


class SpecificCovered(CoopSQL, CoopView):
    '''
        This is the common part of all specific covered parts.

        It will be later used to add extra functionnality (versionned part)
    '''
    pass


class CoveredPerson(SpecificCovered):
    '''
        This is an extension of covered element in the case of a life product.

        In life insurance, we cover persons, so here is a covered person...
    '''
    __name__ = 'ins_contract.covered_person'
    person = fields.Many2One('party.party',
                             'Person')

    @staticmethod
    def get_specific_model_name():
        return 'Covered Person'

    def get_name_for_billing(self):
        return self.person.name


class CoveredCar(SpecificCovered):
    '''
        This is a covered car.
    '''
    __name__ = 'ins_contract.covered_car'


class BrokerManager(CoopSQL, CoopView):
    '''
        This entity will be used to manage the relation between the contract
        and its broker
    '''
    __name__ = 'ins_contract.broker_manager'
    broker = fields.Many2One('party.party',
                             'Broker')
