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
        trytond.tests.test_tryton.install_module('insurance_contract')
        self.SubsProcess = POOL.get('ins_contract.subs_process',
                                          type='wizard')
        self.ProcessDesc = POOL.get('ins_process.process_desc')
        self.SubsProcessDesc, = self.ProcessDesc.search(
                [('process_model', '=', 'ins_contract.subs_process')],
                limit=1)
        self.assert_(self.SubsProcessDesc.id)
        self.Party = POOL.get('party.party')
        self.Product = POOL.get('ins_product.product')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('insurance_contract')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010Contract_creation(self):
        '''
            Tests subscription process
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                 context=CONTEXT) as transaction:
            wizard_id, _, _ = self.SubsProcess.create()
            wizard = self.SubsProcess(wizard_id)
            wizard.transition_steps_start()
            tmp = wizard.project.check_step(
                wizard,
                wizard.process_state.cur_step_desc)
            self.assertEqual(tmp[0], False)


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
