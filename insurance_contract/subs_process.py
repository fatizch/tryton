import datetime

# Needed for storing and displaying objects
from trytond.model import ModelView
from trytond.model import fields as fields

# Needed for Wizardry
from trytond.wizard import Wizard, StateView

# Needed for getting models
from trytond.pool import Pool

# Needed for Evaluation
from trytond.pyson import Eval

from trytond.modules.insurance_process import CoopStep
from trytond.modules.insurance_process import CoopStateView
from trytond.modules.insurance_process import CoopProcess

###############################################################################
# This is the Subscription Process. It is a process (which uses the           #
# CoopProcess framework) which allows to create a contract from scratch.      #
# It asks first for a product, then uses it to calculate things like          #
# eligibility to decide which options will be offered, then finally           #
# creates the contract.                                                       #
###############################################################################


class ProjectState(CoopStep):
    '''
        This step should be the first one, as it asks the user which product
        the contract will be based on, and who will be the client.
    '''
    _name = 'ins_contract.subs_process.project'

    # This will be the effective date of our contract. It is necessary to have
    # it at this step for it decides which product will be available.
    effective_date = fields.Date('Effective Date',
                                 required=True)

    # This is a core field, it will be used all along the process to ask for
    # directions, client side rules, etc...
    product = fields.Many2One('ins_product.product',
                              'Product',
                              domain=[('effective_date',
                                       '<=',
                                       Eval('effective_date'))],
                              depends=['effective_date', ],
                              required=True)

    # Default effective_date is today
    def before_step_init(self, session, data):
        if session.project.effective_date is None:
            session.project.effective_date = datetime.date.today()
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Product Selection'

ProjectState()


class OptionSelectionState(CoopStep):
    '''
        This step uses the provided product to compute a list of available
        options and asks the user to select which one he wants to
        subscribe to.
    '''
    _name = 'ins_contract.subs_process.option_selection'

    # Those are the temporary fields that we will use to represent options.
    # There is no need to give origin and target values, as they are intended
    # solely to provide a way for the user to make his choice.
    options = fields.Many2Many('ins_contract.coverage_displayer',
                               None,
                               None,
                               'Options Choices')

    # We initialize the list of options with the list of coverages offered by
    # the product previously selected.
    def before_step_init_options(self, session, data):
        '''
            This method should not be called when coming from downstream.
            If its from upstream it should.

            Later, we might want to make the 'from upstream' call optionnal,
            depending of what has been changed, but right now we will settle
            for this.
        '''
        options = []
        # Here we assume that there is a step named 'project' with a 'product'
        # field.
        # Later, we might want to use some abstract way to get the product
        # (maybe a method parsing the session states to get one which would
        # match a specific pattern) in order to become state name independant.
        #
        # So we go through the options of our product, then create a displayer
        # which will be used to ask for input from the user.
        for coverage in session.project.product.options:
            options.append({'for_coverage': coverage.id,
                            'from_date': max(coverage.effective_date,
                                             session.project.effective_date),
                           'status': 'Active'})
        # Then set those displayers as the options field of our current step.
        session.option_selection.options = options
        return (True, [])

    # Here we check that at least one option has been selected
    def check_step_option_selected(self, session, data):
        for coverage in session.option_selection.options:
            if coverage.status == 'Active':
                return (True, [])
        return (False, ['At least one option must be active'])

    # and that all options must have an effective date greater than the
    # future contract's effective date.
    def check_step_options_date(self, session, data):
        for coverage in session.option_selection.options:
            if coverage.from_date < session.project.effective_date:
                return (False, ['Options must be subscribed after %s'
                                 % session.project.effective_date])
            elif coverage.from_date < coverage.for_coverage.effective_date:
                return (False, ['%s must be subscribed after %s'
                                % (coverage.for_coverage.name,
                                   coverage.for_coverage.effective_date)])
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Options Selection'

OptionSelectionState()


class SubscriptionProcess(CoopProcess):
    '''
        This class defines the subscription process. It asks the user all that
        will be needed to finally create a contract.
    '''
    _name = 'ins_contract.subs_process'

    @staticmethod
    def coop_process_name():
        return 'Subscription Process'

    # Here we just have to declare our steps
    project = CoopStateView('ins_contract.subs_process.project',
                        'insurance_contract.project_view',)
    option_selection = CoopStateView(
                        'ins_contract.subs_process.option_selection',
                        'insurance_contract.option_selection_view')

    # And do something when validation occurs
    def do_complete(self, session):
        contract_obj = Pool().get('ins_contract.contract')
        options = []
        # We got the list of option displayers, so we create the real thing
        for option in session.option_selection.options:
            options.append(('create',
                            {'effective_date': option.from_date,
                             'coverage': option.for_coverage.id,
                             }))
        # then go for the creation of the contract.
        contract_obj.create({'options': options,
                             'product': session.project.product.id,
                             'effective_date': session.project.effective_date,
                             'contract_number': contract_obj.
                                                    get_new_contract_number()
                             })
        # Do not forget to return a 'everything went right' signal !
        return (True, [])

SubscriptionProcess()
