import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction

from trytond.model import fields as fields

from trytond.exceptions import UserError

from trytond.modules.insurance_process import CoopProcess, ProcessState
from trytond.modules.insurance_process import CoopStep, CoopStateView

from trytond.modules.coop_utils import model as model
from trytond.modules.coop_utils import utils as utils

MODULE_NAME = os.path.basename(
                  os.path.abspath(
                      os.path.join(os.path.normpath(__file__), '..', '..')))


class DummyObject(model.CoopSQL, model.CoopView):
    '''
        A dummy Object for our DummyProcess
    '''
    __name__ = 'ins_process.dummy_object'
    contract_number = fields.Char('Contract Number')


class DummyStep(CoopStep):
    '''
        a DummyStep for a DummyProcess
    '''
    # This is a step. It inherits from CoopStep, and has one attribute (name).
    __name__ = 'ins_process.dummy_process.dummy_step'
    name = fields.Char('Name')

    # This is its user-friendly name for creating the step desc
    @staticmethod
    def coop_step_name():
        return 'Dummy Step'

    # This is a before method, which will be useful to initialize our name
    # field. If we had a One2Many field, we could create objects and use their
    # fields to compute the default value of another.
    @staticmethod
    def before_step_init(wizard):
        wizard.dummy_step.name = 'Toto'
        return (True, [])

    # Those are validation methods which will be called by the check_step
    # method.
    # DO NOT FORGET to always return something
    @staticmethod
    @utils.priority(1)
    def check_step_schtroumpf_validation(wizard):
        if wizard.dummy_step.name == 'Toto':
            return (False, ['Schtroumpf'])
        return (True, [])

    @staticmethod
    @utils.priority(2)
    def check_step_kiwi_validation(wizard):
        if wizard.dummy_step.name == 'Toto':
            return (False, ['Kiwi'])
        return (True, [])

    @staticmethod
    def check_step_abstract_obj(wizard):
        if 'for_contract' in utils.WithAbstract.abstract_objs(wizard):
            contract = utils.WithAbstract.get_abstract_objects(wizard,
                                                        'for_contract')
            if hasattr(contract, 'contract_number'):
                contract.contract_number = 'Toto'
            else:
                contract.contract_number = 'Test'
            utils.WithAbstract.save_abstract_objects(wizard,
                                              ('for_contract', contract))
            return (True, [])
        else:
            return (False, ['Could not find for_contract'])


class DummyStep1(CoopStep):
    '''
        Another DummyStep for our DummyProcess
    '''
    # This is another dummy step
    __name__ = 'ins_process.dummy_process.dummy_step1'
    name = fields.Char('Name')

    # We initialize this step with some data from the previous step
    @staticmethod
    def before_step_init(wizard):
        # We cannot be sure that the current process uses a 'dummy_step',
        # so we test for one.
        # We also could make the state mandatory with else return (False, [..])
        if hasattr(wizard, 'dummy_step'):
            wizard.dummy_step1.name = wizard.dummy_step.name
        return (True, [])

    @staticmethod
    def check_step_abstract(wizard):
        for_contract, for_contract1 = utils.WithAbstract.get_abstract_objects(
                                                        wizard,
                                                        ['for_contract',
                                                         'for_contract1'])
        for_contract1.contract_number = for_contract.contract_number
        utils.WithAbstract.save_abstract_objects(wizard, ('for_contract1',
                                                  for_contract1))
        return (False, [wizard.process_state.for_contract_str,
                        wizard.process_state.for_contract1_str])

    @staticmethod
    def coop_step_name():
        return 'Dummy Step 1'


class DummyProcessState(ProcessState, utils.WithAbstract):
    '''
        A DummyProcessState with abstract objects, for tests...
    '''
    __name__ = 'ins_process.dummy_process_state'
    __abstracts__ = [('for_contract', 'ins_process.dummy_object'),
                     ('for_contract1', 'ins_process.dummy_object'),
                     ]


class DummyProcess(CoopProcess):
    '''
        A DummyProcess for test processing
    '''
    # This is a Process. It inherits of model.CoopProcess.
    __name__ = 'ins_process.dummy_process'

    config_data = {
        'process_state_model': 'ins_process.dummy_process_state'
        }

    # We just need to declare the two steps
    dummy_step = CoopStateView('ins_process.dummy_process.dummy_step',
                               # Remember, the view name must start with the
                               # tryton module name !
                               'insurance_process.dummy_view')
    dummy_step1 = CoopStateView('ins_process.dummy_process.dummy_step1',
                               'insurance_process.dummy_view')

    # and give it a name.
    @staticmethod
    def coop_process_name():
        return 'Dummy Process Test'

    def do_complete(self):
        # Create and store stuff
        return (True, [])


class ModuleTestCase(unittest.TestCase):
    '''
    Test Coop module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module(MODULE_NAME)
        self.process_desc = POOL.get('ins_process.process_desc')
        self.step_desc = POOL.get('ins_process.step_desc')
        self.step_method_desc = POOL.get('ins_process.step_method_desc')
        self.coop_process = POOL.get('ins_process.coop_process',
                                         type='wizard')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view(MODULE_NAME)

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def add_pool(self):
        POOL.add(DummyObject)
        POOL.add(DummyStep)
        POOL.add(DummyStep1)
        POOL.add(DummyProcessState)
        POOL.add(DummyProcess, type='wizard')
        self.dummy_process = POOL.get('ins_process.dummy_process',
                                          type='wizard')
        self.dummy_step = POOL.get('ins_process.dummy_process.dummy_step')
        self.dummy_step1 = \
                            POOL.get('ins_process.dummy_process.dummy_step1')

    def register(self, objs, type, module):
        map(lambda x: x.__setup__(), objs)
        map(lambda x: x.__post_setup__(), objs)
        map(lambda x: POOL.register(x, type_=type, module=module), objs)

    def register_pool(self):
        self.register(
            [DummyObject, DummyStep, DummyStep1, DummyProcessState],
            'model', 'insurance_process')
        self.register([DummyProcess], 'wizard', 'insurance_process')

    def test0010ProcessDesc_creation(self):
        '''
            Tests process desc creation
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
            self.register_pool()
            self.add_pool()
            steps = []
            steps.append(('create', {
                'sequence': 1,
                'step_model': self.dummy_step.__name__
                                    }))
            steps.append(('create', {
                'sequence': 2,
                'step_model': self.dummy_step1.__name__
                                     }))
            process_desc = self.process_desc.create({
                'name': 'Contract Subscription',
                'steps': steps,
                'process_model': self.dummy_process.__name__
                                                           })
            self.assert_(process_desc.id)
            transaction.cursor.commit()
            self.process_desc = process_desc
            for step in process_desc.steps:
                if step.sequence == 1:
                    self.assertEqual(step.step_model,
                                     self.dummy_step.__name__,
                                     'Fail first step')
                elif step.sequence == 2:
                    self.assertEqual(step.step_model,
                                     self.dummy_step1.__name__,
                                     'Fail second step')

    def create_dummy_process_desc(self):
        sd = self.step_desc()
        sd.button_next = True
        sd.button_previous = False
        sd.button_check = True
        sd.button_complete = False
        sd.button_cancel = False
        sd.button_suspend = True
        sd.button_default = 'button_next'
        sd.sequence = 1
        sd.step_model = 'ins_process.dummy_process.dummy_step'

        sd1 = self.step_desc()
        sd1.button_next = False
        sd1.button_previous = True
        sd1.button_check = True
        sd1.button_complete = False
        sd1.button_cancel = True
        sd1.button_suspend = False
        sd1.button_default = 'button_cancel'
        sd1.sequence = 2
        sd1.step_model = 'ins_process.dummy_process.dummy_step1'

        dp = self.process_desc()
        dp.process_model = 'ins_process.dummy_process'
        dp.steps = [sd, sd1]
        dp.save()

    def test0011DummyProcess(self):
        '''
            Tests dummyprocess running
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                context=CONTEXT) as transaction:
            self.add_pool()
            self.create_dummy_process_desc()
            wizard_id, _, _ = self.coop_process.create()
            wizard = self.coop_process(wizard_id)
            self.assertRaises(UserError,
                              self.coop_process.transition_steps_start,
                              wizard)
            wizard_id, _, _ = self.dummy_process.create()
            wizard = self.dummy_process(wizard_id)
            wizard.transition_steps_start()
            process_desc, = self.process_desc.search([
                                                ('process_model',
                                                '=',
                                                self.dummy_process.__name__)],
                                                        limit=1)
            self.assertEqual(wizard.process_state.cur_step,
                             'dummy_step',
                             'Wrong first step !')
            self.assertEqual(wizard.process_state.cur_step_desc,
                             process_desc.steps[0],
                             'Wrong first step desc')
            self.assertEqual(process_desc,
                             wizard.process_state.process_desc,
                             'Wrong process desc !')
            self.assertEqual('Toto',
                             wizard.dummy_step.name,
                             'Before Step Failed !')
            self.assertTupleEqual(
                        wizard.dummy_step.check_step(
                                    wizard,
                                    wizard.process_state.cur_step_desc
                                                      ),
                        (False, ['Kiwi', 'Schtroumpf']))
            wizard.transition_steps_check()
            self.assertRaises(UserError,
                            wizard.transition_master_step)
            wizard.transition_steps_next()
            self.assertRaises(UserError,
                              wizard.transition_master_step)
            wizard.dummy_step.name = 'Titi'
            self.assertTupleEqual(
                        wizard.dummy_step.check_step(
                                    wizard,
                                    wizard.process_state.cur_step_desc
                                                      ),
                        (True, []))
            wizard.transition_steps_next()
            wizard.transition_master_step()
            self.assertEqual(wizard.process_state.cur_action,
                             'go_next')
            self.assertEqual(wizard.process_state.cur_step,
                             'dummy_step1')
            self.assertEqual(wizard.dummy_step1.name,
                             'Titi')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
