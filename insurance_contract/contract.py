import datetime

# Needed for storing and displaying objects
from trytond.model import ModelSQL, ModelView
from trytond.model import fields as fields

# Needed for Wizardry
from trytond.wizard import Wizard, Button, StateView, StateTransition

# Needed for Eval
from trytond.pyson import Eval

# Needed for getting models
from trytond.pool import Pool

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
    _name = 'ins_contract.subs_manager'
    _description = __doc__

SubscriptionManager()


class GenericExtension(ModelSQL, ModelView):
    '''
    This class will contains all data that are non-specific to the product
    used for the contract.
    '''
    _name = 'ins_contract.gen_extension'
    _description = 'Extension'

GenericExtension()


class ProductExtension(ModelSQL, ModelView):
    '''
    Here comes the Extension which will contains all data needed by a specific
    product to compute rates, benefits etc.

    It should includes all coverage data, whether we are dealing with life
    insurance or PnC, each one of those is just a bunch of data that will be
    used in the business rules to calculate stuff.
    '''
    _name = 'ins_contract.prod_extension'
    _description = 'Product Extension'

ProductExtension()


class Contract(ModelSQL, ModelView):
    '''
    This class represents the contract, and will be at the center of
    many business processes.
    '''
    _name = 'ins_contract.contract'
    _description = 'Contrat'

    # Effective date is the date at which the contract "starts" :
    #    The client pays its premium
    #    Claims can be declared
    effective_date = fields.Date('Effective Date',
                                 required=True)

    # Management date is the date at which the company started to manage the
    # contract. Default value is effective_date
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
    options = fields.One2Many('ins_contract.options',
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

    # The generic extension will contain complementary data which is not
    # specific to the product. It just gives us a place to store additional
    # data which does not depend on the product chosen by the subscriber.
    generic_extension = fields.Many2One('ins_contract.gen_extension',
                                        'Extension')

    # On the other hand, the Product Extension will represents all product
    # specific data, including coverages description. It will be one major
    # element used in most of the product specific business rules.
    product_extension = fields.Many2One('ins_contract.prod_extension',
                                        'Product Extension')

    @staticmethod
    def get_new_contract_number():
        return 'Ct00000001'

Contract()


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
    _name = 'ins_contract.options'
    _description = 'Option'

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
    effective_date = fields.Date('Effective Date',
                                 required=True)

Option()


class CoverageDisplayer(ModelView):
    '''
        This class is a displayer, that is a class which will only be used
        to show something (or ask for something) to the user. It needs not
        to be stored, and is not supposed to be.
    '''
    _name = 'ins_contract.coverage_displayer'
    for_coverage = fields.Many2One('ins_product.coverage',
                                   'Coverage',
                                   readonly=True)
    from_date = fields.Date(
                        'From Date',
                        domain=[('for_coverage.effective_date',
                                 '<=',
                                 'from_date')],
                        depends=['for_coverage', ],
                        required=True)
    status = fields.Selection(OPTIONSTATUS,
                              'Status')

CoverageDisplayer()
