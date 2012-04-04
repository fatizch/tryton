from trytond.model import ModelView, ModelSQL
from trytond.model import fields as fields

CONTRACTNUMBER_MAX_LENGTH = 10

class Contract(ModelSQL, ModelView):
    '''
    This class represents the contract, and will be at the center of many business processes.
    '''
    _name = 'ins_contract.contract'
    _description = __doc__
    
    # Effective date is the date at which the contract "starts" :
    #    The client pays its premium
    #    Claims can be declared
    effective_date = fields.Date('Effective Date',
                                 required=True)
    
    # Management date is the date at which the company started to manage the contract
    start_management_date = fields.Date('Management Date')
    
    # Contract Number will be the number which will be used to reference the contract
    # for external uses (forms, other softwares...) 
    contract_number = fields.Char('Contract Number',
                                  required=True,
                                  select=1,
                                  size=CONTRACTNUMBER_MAX_LENGTH)
    
    # The option list is very important, as it is what really "makes" the contract.
    # Almost all the main actions on the contract will use either one or all options.
    # If you want to generate an invoice, you need the options
    # If you want to pay for a claim, you got to check the options to know
    # whether you got to do so or not, and if you do how much you will pay
    options = fields.One2Many('ins_contract.options',
                              'contract',
                              'Options')
    
    # Each contract will be build from an offered product, which will give access to a number
    # of business rules. Those rules will be used all along the contract's life, so we need
    # to easily get access to them, through a direct link to the product 
    product = fields.Many2One('ins_product.product',
                              'Product',
                              required=True)
    
    # The subscriber is the client which did (or will) sign the contract.
    # It is an important part of the contract life, as he usually is the recipient
    # of the letters of the contract, he will pay the premium etc...
    #
    # Some business rules might need some of the subscriber's data to compute. 
    subscriber = fields.Many2One('party.party',
                                 'Subscriber',
                                 required=True)
    
Contract()

class Option(ModelSQL, ModelView):
    '''
    This class is an option, that is a global coverage which will be applied to all
    covered persons on the contract.
    
    An instance is based on a product.coverage, which is then customized at subscription
    time in order to let the client decide precisely what he wants.
    
    Typically, on a life contract, the product.coverage might allow a choice of coverage amount.
    The Option will store the choice of the client at subscription time, so that it can be
    used later when calculating premium or benefit. 
    '''
    _name = 'ins_contract.options'
    _description = __doc__
    
    # Every option is linked to a contract (and only one !)
    # Also, if the contract is destroyed, so should the option 
    contract = fields.Many2One('ins_contract.contract',
                               'Contract',
                               ondelete='CASCADE')
    
    # The option is build from a model, the product.coverage, and then customized
    # depending on the client's desiderata. But the offered coverage provides all
    # the business rules for the option life : premium calculation rules, benefit rules
    # eligibility rules, etc...
    # Almost all actions performed on an option will require a call to a business rule
    # of the offered coverage
    coverage = fields.Many2One('ins_product.coverage',
                               'Offered Coverage',
                               required=True)
    
Option()
