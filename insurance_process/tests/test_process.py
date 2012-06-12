# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction

# Needed for wizardry testing
from trytond.wizard import Wizard
from trytond.exceptions import UserError


class ProcessTestCase(unittest.TestCase):
    def setUp(self):
        trytond.tests.test_tryton.install_module('insurance_process')
        self.process_desc = POOL.get('ins_process.process_desc')
        self.step_desc = POOL.get('ins_process.step_desc')
        self.step_method_desc = POOL.get('ins_process.step_method_desc')
        self.dummy_process = POOL.get('ins_process.dummy_process',
                                          type='wizard')
        self.dummy_step = POOL.get('ins_process.dummy_process.dummy_step')
        self.dummy_step1 = \
                            POOL.get('ins_process.dummy_process.dummy_step1')
        self.coop_process = POOL.get('ins_process.coop_process',
                                         type='wizard')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('insurance_process')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010ProcessDesc_creation(self):
        '''
            Tests process desc creation
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
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

    def test0011DummyProcess(self):
        '''
            Tests dummyprocess running
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                context=CONTEXT) as transaction:
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
        ProcessTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
