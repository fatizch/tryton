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
from trytond.modules.insurance_process import ProcessState
from trytond.modules.insurance_process import WithAbstract
from trytond.modules.insurance_process import AbstractObject
from trytond.modules.insurance_process import DependantState
from trytond.modules.insurance_process import CoopView
from trytond.modules.coop_utils import get_descendents
from trytond.model.browse import BrowseRecordNull

from trytond.transaction import Transaction
from trytond.modules.insurance_contract import OPTIONSTATUS

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
    start_date = fields.Date('Effective Date',
                                 required=True)

    # The subscriber is the client which wants to subscribe to a contract.
    subscriber = fields.Many2One('party.party',
                                 'Subscriber')

    # This is a core field, it will be used all along the process to ask for
    # directions, client side rules, etc...
    product = fields.Many2One('ins_product.product',
                              'Product',
                              # domain : a list of conditions
                              # (param1, op, param2).
                              # Param1 must be a field of the target model,
                              # Param2 will be evaluated in the current record
                              # context, so will return the value of
                              # start_date in the current ProjetState
                              domain=[('start_date',
                                       '<=',
                                       Eval('start_date', None))],
                              depends=['start_date', ],
                              required=True)

    # Default start_date is today
    def before_step_init(self, session):
        if session.project.start_date is None:
            session.project.start_date = datetime.date.today()
        return (True, [])

    def check_step_product(self, session):
        if type(session.project.product) != BrowseRecordNull:
            return (True, [])
        return (False, ['A product must be provided !'])

    def check_step_subscriber(self, session):
        if type(session.project.subscriber) != BrowseRecordNull:
            return (True, [])
        return (False, ['A subscriber must be provided !'])

    def post_step_update_abstract(self, session):
        contract = WithAbstract.get_abstract_objects(session, 'for_contract')
        contract.product = session.project.product
        contract.start_date = session.project.start_date
        contract.subscriber = session.project.subscriber
        WithAbstract.save_abstract_objects(session, ('for_contract', contract))
        return (True, [])

    def post_step_update_on_product(self, session):
        session.process_state.on_product = session.project.product.id
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Product Selection'

ProjectState()


class CoverageDisplayer(CoopView):
    '''
        This class is a displayer, that is a class which will only be used
        to show something (or ask for something) to the user. It needs not
        to be stored, and is not supposed to be.
    '''
    _name = 'ins_contract.coverage_displayer'
    coverage = fields.Many2One('ins_product.coverage',
                                   'Coverage',
                                   readonly=True)
    start_date = fields.Date(
                        'From Date',
                        domain=[('coverage.start_date',
                                 '<=',
                                 'start_date')],
                        depends=['coverage', ],
                        required=True)
    status = fields.Selection(OPTIONSTATUS,
                              'Status')

CoverageDisplayer()


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
    def before_step_init_options(self, session):
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
            options.append({'coverage': coverage.id,
                            'start_date': max(coverage.start_date,
                                             session.project.start_date),
                           'status': 'Active'})
        # Then set those displayers as the options field of our current step.
        session.option_selection.options = options
        return (True, [])

    # Here we check that at least one option has been selected
    def check_step_option_selected(self, session):
        for coverage in session.option_selection.options:
            if coverage.status == 'Active':
                return (True, [])
        return (False, ['At least one option must be active'])

    # and that all options must have an effective date greater than the
    # future contract's effective date.
    def check_step_options_date(self, session):
        for coverage in session.option_selection.options:
            if coverage.start_date < session.project.start_date:
                return (False, ['Options must be subscribed after %s'
                                 % session.project.start_date])
            elif coverage.start_date < coverage.coverage.start_date:
                return (False, ['%s must be subscribed after %s'
                                % (coverage.coverage.name,
                                   coverage.coverage.start_date)])
        return (True, [])

    def post_step_create_options(self, session):
        contract = WithAbstract.get_abstract_objects(session, 'for_contract')
        list_options = []
        for option in session.option_selection.options:
            list_options.append(AbstractObject('ins_contract.options', 0,
                                               init_data=option))
        contract.options = list_options
        WithAbstract.save_abstract_objects(session, ('for_contract', contract))
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Options Selection'

OptionSelectionState()


class CoveredDataDesc(CoopView):
    _name = 'ins_contract.subs_process.covered_data_desc'
    covered_element = fields.Reference('Covered Element',
                                       selection='get_covered_elem_model')
    #covered_element = fields.Many2One(
     #                   'ins_contract.subs_process.covered_person_desc',
      #                  'Covered Element')

    status = fields.Selection(OPTIONSTATUS, 'Status')

    start_date = fields.Date('Start Date')

    end_date = fields.Date('End Date')

    for_coverage = fields.Many2One('ins_product.coverage',
                                   'For coverage')

    def get_covered_elem_model(self):
        return get_descendents(DependantState)

CoveredDataDesc()


class CoveredElementDesc(CoopView):
    covered_data = fields.One2Many(
                            'ins_contract.subs_process.covered_data_desc',
                            'covered_element',
                            'Covered Data')


class CoveredPersonDesc(CoveredElementDesc):
    _name = 'ins_contract.subs_process.covered_person_desc'

    person = fields.Many2One('party.party',
                             'Covered Person')
    life_state = fields.Many2One('ins_contract.subs_process.extension_life',
                                 'Life State')
    toto = fields.Char('Test')

    def default_toto(self):
        return CoveredPersonDesc.get_context().data[
                                                'process_state']['cur_step']

CoveredPersonDesc()


class ExtensionLifeState(DependantState):
    _name = 'ins_contract.subs_process.extension_life'
    covered_elements = fields.One2Many(
                            'ins_contract.subs_process.covered_person_desc',
                            'life_state',
                            'Covered Elements')

    @staticmethod
    def depends_on_state():
        return 'extension'

    @staticmethod
    def state_name():
        return 'extension_life'

    def before_step_subscriber_as_covered(self, session):
        covered_data = []
        for coverage in session.option_selection.options:
            if coverage.status == 'Active':
                covered_data.append({
                                'status': 'Active',
                                'start_date': coverage.start_date,
                                'for_coverage': coverage.coverage.id
                                     })
        session.extension_life.covered_elements = []
        session.extension_life.covered_elements.append(
                                    {'person': session.project.subscriber.id,
                                     'toto': 'Titi',
                                     'covered_data': covered_data
                                     })
        return (True, [])

ExtensionLifeState()


class SubscriptionProcessState(ProcessState, WithAbstract):
    __abstracts__ = [('for_contract', 'ins_contract.contract')]
    _name = 'ins_contract.subs_process.process_state'

SubscriptionProcessState()


class SubscriptionProcess(CoopProcess):
    '''
        This class defines the subscription process. It asks the user all that
        will be needed to finally create a contract.
    '''
    _name = 'ins_contract.subs_process'

    process_state = StateView('ins_contract.subs_process.process_state',
                              '',
                              [])

    @staticmethod
    def coop_process_name():
        return 'Subscription Process'

    # Here we just have to declare our steps
    project = CoopStateView('ins_contract.subs_process.project',
                        'insurance_contract.project_view',)
    option_selection = CoopStateView(
                        'ins_contract.subs_process.option_selection',
                        'insurance_contract.option_selection_view')
    extension_life = CoopStateView(
                        'ins_contract.subs_process.extension_life',
                        'insurance_contract.extension_life_view')

    # And do something when validation occurs
    def do_complete(self, session):
        contract_obj = Pool().get('ins_contract.contract')
        contract = WithAbstract.get_abstract_objects(session, 'for_contract')
        options = []
        # We got the list of option displayers, so we create the real thing
        for option in contract.options:
            options.append(('create',
                            {'start_date': option.start_date,
                             'coverage': option.coverage.id,
                             }))
        # then go for the creation of the contract.
        contract_obj.create({'options': options,
                             'product': contract.product.id,
                             'start_date': contract.start_date,
                             'contract_number': contract_obj.
                                                    get_new_contract_number()
                             })
        # Do not forget to return a 'everything went right' signal !
        return (True, [])

SubscriptionProcess()
