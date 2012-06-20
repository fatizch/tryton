# Needed for storing and displaying objects
from trytond.model import ModelSQL, ModelView
from trytond.model import fields as fields

# Needed for getting models
from trytond.pool import Pool

from trytond.modules.coop_utils import get_descendents

__all__ = [
        'SubscriptionManager',
        'Contract',
        'Option',
        'BillingManager',
        'CoveredElement',
        'CoveredData',
        'ExtensionLife',
        'ExtensionCar',
        'CoveredPerson',
        'CoveredCar',
        'BrokerManager'
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


class SubscriptionManager(ModelSQL, ModelView):
    '''
        The subscription Manager will be used to store subscription-only
        related data.
    '''
    __name__ = 'ins_contract.subs_manager'


class GenericExtension(ModelSQL, ModelView):
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


class Contract(ModelSQL, ModelView):
    '''
    This class represents the contract, and will be at the center of
    many business processes.
    '''
    __name__ = 'ins_contract.contract'

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

    # The billing manager will be in charge of all billing-related actions.
    # The select statements for billing will use this object to get the list
    # of tasks
    billing_manager = fields.One2Many('ins_contract.billing_manager',
                                      'contract',
                                      'Billing Manager')

    extension_life = fields.Many2One('ins_contract.extension_life',
                                     'Life Extension')

    extension_car = fields.Many2One('ins_contract.extension_car',
                                    'Car Extension')

    broker_manager = fields.Many2One('ins_contract.broker_manager',
                                     'Broker Manager')

    @staticmethod
    def get_new_contract_number():
        return 'Ct00000001'

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


class Option(ModelSQL, ModelView):
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
        return [(model__name__, model.get_option_data__name__())
                for (model__name__, model) in Pool().iterobject()
                if hasattr(model, 'get_option_data__name__')
                    and model.get_option_data__name__() != '']


class BillingManager(ModelSQL, ModelView):
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


class CoveredElement(ModelSQL, ModelView):
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


class CoveredData(ModelSQL, ModelView):
    '''
        Covered Datas are the link between covered elements and options.

        Basically, it is the start and end date of covering.
    '''
    __name__ = 'ins_contract.covered_data'
    for_covered = fields.Many2One('ins_contract.covered_element',
                                  'Covered Element')
    for_coverage = fields.Many2One('ins_product.coverage',
                                   'Coverage')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


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


class CoveredPerson(ModelSQL, ModelView):
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


class CoveredCar(ModelSQL, ModelView):
    '''
        This is a covered car.
    '''
    __name__ = 'ins_contract.covered_car'


class BrokerManager(ModelSQL, ModelView):
    '''
        This entity will be used to manage the relation between the contract
        and its broker
    '''
    __name__ = 'ins_contract.broker_manager'
    broker = fields.Many2One('party.party',
                             'Broker')
