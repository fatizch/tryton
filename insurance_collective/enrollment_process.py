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

from trytond.modules.insurance_contract import ProjectState
from trytond.modules.insurance_contract import SubscriptionProcess

###############################################################################
# This is the Subscription Process. It is a process (which uses the           #
# CoopProcess framework) which allows to create a contract from scratch.      #
# It asks first for a product, then uses it to calculate things like          #
# eligibility to decide which options will be offered, then finally           #
# creates the contract.                                                       #
###############################################################################

__all__ = [
        'ProjectStateEnrollment',
        'EnrollmentProcess',
        'EnrollmentProcessState',
           ]


class ProjectStateEnrollment(ProjectState):
    '''
        This step should be the first one, as it asks the user which product
        the contract will be based on, and who will be the client.
    '''
    __name__ = 'ins_collective.enrollment_process.project'

    # This is a core field, it will be used all along the process to ask for
    # directions, client side rules, etc...
    product = fields.Many2One('ins_collective.product',
                              'Product')

    on_contract = fields.Many2One(
        'ins_collective.gbp_contract',
        'GBP Contract')

    # Override this control, it is not the same as before.
    @staticmethod
    def check_step_product(wizard):
        if hasattr(wizard.project, 'on_contract'):
            return (True, [])
        return (False, ['A GBP contract must be provided !'])

    # Override as well, we want the product to come from the contract
    @staticmethod
    def post_step_update_abstract(wizard):
        wizard.project.product = wizard.project.on_contract.final_product
        return ProjectState.post_step_update_abstract(wizard)

    @staticmethod
    def coop_step_name():
        return 'GBP Contract Selection'


class EnrollmentProcessState(ProcessState, WithAbstract):
    '''
        The process state for the subscription process must have an abstract
        contract.
    '''
    __abstracts__ = [('for_contract', 'ins_collective.enrollment')]
    __name__ = 'ins_collective.enrollment_process.process_state'


class EnrollmentProcess(SubscriptionProcess):
    '''
        This class defines the enrollment process.
    '''
    __name__ = 'ins_collective.enrollment_process'

    project = CoopStateView('ins_collective.enrollment_process.project',
                            'insurance_collective.enrollment_project_view')
