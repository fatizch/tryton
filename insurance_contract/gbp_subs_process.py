import datetime

from trytond.model import fields as fields

# Needed for Wizardry
from trytond.wizard import StateView

# Needed for getting models
from trytond.pool import Pool

# Needed for Evaluation
from trytond.pyson import Eval

from trytond.modules.insurance_process import CoopProcess
from trytond.modules.insurance_process import ProcessState
from trytond.modules.insurance_process import CoopStep
from trytond.modules.insurance_process import CoopStateView
from trytond.modules.insurance_process import WithAbstract
from trytond.modules.insurance_process import DependantState
from trytond.modules.insurance_process import CoopView
from trytond.modules.coop_utils import get_descendents

from contract import OPTIONSTATUS

###############################################################################
# This is the Subscription Process. It is a process (which uses the           #
# CoopProcess framework) which allows to create a contract from scratch.      #
# It asks first for a product, then uses it to calculate things like          #
# eligibility to decide which options will be offered, then finally           #
# creates the contract.                                                       #
###############################################################################

__all__ = [
        'ProjectGBPState',
        'ExtensionGBPState',
        'GBPSubscriptionProcessState',
        'GBPSubscriptionProcess',
           ]


class ProjectGBPState(CoopStep):
    '''
        This step should be the first one, as it asks the user which product
        the contract will be based on, and who will be the client.
    '''
    __name__ = 'ins_contract.gbp_subs_process.project'

    # This will be the effective date of our contract. It is necessary to have
    # it at this step for it decides which product will be available.
    start_date = fields.Date('Effective Date')

    # The subscriber is the client which wants to subscribe to a contract.
    subscriber = fields.Many2One('party.party',
                                 'Subscriber')

    broker = fields.Many2One('party.party',
                             'Broker',
                             states={'invisible': ~Eval('product')})

    # Default start_date is today
    @staticmethod
    def before_step_init(wizard):
        if not hasattr(wizard.project, 'start_date'):
            wizard.project.start_date = datetime.date.today()
        return (True, [])

    @staticmethod
    def check_step_subscriber(wizard):
        if hasattr(wizard.project, 'subscriber'):
            return (True, [])
        return (False, ['A subscriber must be provided !'])

    @staticmethod
    def check_step_effective_date(wizard):
        if hasattr(wizard.project, 'start_date'):
            return (True, [])
        return (False, ['An effective date is necessary'])

    @staticmethod
    def post_step_update_abstract(wizard):
        BrokerManager = Pool().get('ins_contract.broker_manager')
        contract = WithAbstract.get_abstract_objects(wizard, 'for_contract')
        contract.start_date = wizard.project.start_date
        contract.subscriber = wizard.project.subscriber
        if hasattr(wizard.project, 'broker'):
            broker_manager = BrokerManager()
            broker_manager.broker = wizard.project.broker
            contract.broker_manager = broker_manager
        WithAbstract.save_abstract_objects(wizard, ('for_contract', contract))
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Start GBP Subscription'


class ExtensionGBPState(CoopStep):
    '''
        This a process step which will be used for Life product subscriptions.
    '''
    __name__ = 'ins_contract.gbp_subs_process.extension_gbp'

    contact = fields.Many2One(
        'party.party',
        'Subscriber Contact')

    final_product = fields.One2Many(
        'ins_product.product',
        None,
        'Final Product')

    @staticmethod
    def depends_on_state():
        return 'extension'

    @staticmethod
    def state_name():
        return 'extension_gbp'

    @staticmethod
    def check_step_contact_exists(wizard):
        if hasattr(wizard.extension_gbp, 'contact'):
            if wizard.extension_gbp.contact:
                return (True, [])
        return (False, ['A contact must be provided'])

    @staticmethod
    def check_step_final_product(wizard):
        res, errors = (True, [])
        if hasattr(wizard.extension_gbp, 'final_product'):
            if len(wizard.extension_gbp.final_product) == 1:
                product = wizard.extension_gbp.final_product[0]
                if product.start_date < wizard.project.start_date:
                    res = False
                    errors.append(
                        'Product effective date must be greater than %s'
                        % wizard.project.start_date)
                return (res, errors)
            elif len(wizard.extension_gbp.final_product) > 1:
                return (False, ['There must be only one product !'])
        return (False, ['A product is necessary'])

    @staticmethod
    def post_step_update_contract(wizard):
        contract = WithAbstract.get_abstract_objects(wizard, 'for_contract')
        contract.contact = wizard.extension_gbp.contact
        contract.final_product = wizard.extension_gbp.final_product[0]
        WithAbstract.save_abstract_objects(wizard, ('for_contract', contract))
        return (True, [])

    @staticmethod
    def coop_step_name():
        return 'Define your product'


class GBPSubscriptionProcessState(ProcessState, WithAbstract):
    '''
        The process state for the subscription process must have an abstract
        contract.
    '''
    __abstracts__ = [('for_contract', 'ins_contract.gbp_contract')]
    __name__ = 'ins_contract.gbp_subs_process.process_state'


class GBPSubscriptionProcess(CoopProcess):
    '''
        This class defines the subscription process. It asks the user all that
        will be needed to finally create a contract.
    '''
    __name__ = 'ins_contract.gbp_subs_process'

    process_state = StateView('ins_contract.gbp_subs_process.process_state',
                              '',
                              [])

    @staticmethod
    def coop_process_name():
        return 'GBP Subscription Process'

    # Here we just have to declare our steps
    project = CoopStateView('ins_contract.gbp_subs_process.project',
                            'insurance_contract.gbp_project_view')
    extension_gbp = CoopStateView(
        'ins_contract.gbp_subs_process.extension_gbp',
        'insurance_contract.gbp_extension_view')

    # And do something when validation occurs
    def do_complete(self):
        contract = WithAbstract.get_abstract_objects(self, 'for_contract')
        # contract.extension_life.save()
        contract.contract_number = contract.get_new_contract_number()

        contract.save()

        # Do not forget to return a 'everything went right' signal !
        return (True, [])
