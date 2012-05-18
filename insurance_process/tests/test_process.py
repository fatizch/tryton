# Needed for python test management
import unittest

# Needed for tryton test integration
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction

# Needed for wizardry testing
from trytond.wizard import Session
from trytond.exceptions import UserError
from trytond.model.browse import BrowseRecord


class ProcessTestCase(unittest.TestCase):
    def setUp(self):
        trytond.tests.test_tryton.install_module('insurance_process')
        self.process_desc_obj = POOL.get('ins_process.process_desc')
        self.step_desc_obj = POOL.get('ins_process.step_desc')
        self.step_method_desc_obj = POOL.get('ins_process.step_method_desc')
        self.dummy_process_obj = POOL.get('ins_process.dummy_process',
                                          type='wizard')
        self.dummy_step_obj = POOL.get('ins_process.dummy_process.dummy_step')
        self.dummy_step1_obj = \
                            POOL.get('ins_process.dummy_process.dummy_step1')
        self.coop_process_obj = POOL.get('ins_process.coop_process',
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
                'order': 1,
                'step_model': self.dummy_step_obj._name
                                    }))
            steps.append(('create', {
                'order': 2,
                'step_model': self.dummy_step1_obj._name
                                     }))
            process_desc_id = self.process_desc_obj.create({
                'name': 'Contract Subscription',
                'steps': steps,
                'number_of_steps': 2,
                'process_model': self.dummy_process_obj._name
                                                           })
            self.assert_(process_desc_id)
            transaction.cursor.commit()
            self.process_desc = process_desc_id
            process = self.process_desc_obj.browse(process_desc_id)
            for step in process.steps:
                if step.order == 1:
                    self.assertEqual(step.step_model,
                                     self.dummy_step_obj._name,
                                     'Fail first step')
                elif step.order == 2:
                    self.assertEqual(step.step_model,
                                     self.dummy_step1_obj._name,
                                     'Fail second step')

    def test0011DummyProcess(self):
        '''
            Tests dummyprocess running
        '''
        with Transaction().start(DB_NAME,
                                 USER,
                                context=CONTEXT) as transaction:
            session_id, _, _ = self.coop_process_obj.create()
            session = Session(self.coop_process_obj, session_id)
            self.assertRaises(UserError,
                              self.coop_process_obj.transition_steps_start,
                              session)
            session_id, _, _ = self.dummy_process_obj.create()
            session = Session(self.dummy_process_obj, session_id)
            self.dummy_process_obj.transition_steps_start(session)
            process_desc_id = self.process_desc_obj.search([
                                                ('process_model',
                                                '=',
                                                self.dummy_process_obj._name)],
                                                        limit=1)[0]
            process_desc = self.process_desc_obj.browse(process_desc_id)
            self.assertEqual(session.process_state.cur_step,
                             'dummy_step',
                             'Wrong first step !')
            self.assertEqual(session.process_state.cur_step_desc,
                             process_desc.steps[0],
                             'Wrong first step desc')
            self.assertEqual(process_desc,
                             session.process_state.process_desc,
                             'Wrong process desc !')
            self.assertEqual('Toto',
                             session.dummy_step.name,
                             'Before Step Failed !')
            self.assertTupleEqual(
                        self.dummy_step_obj.check_step(
                                    session,
                                    {},
                                    session.process_state.cur_step_desc
                                                      ),
                        (False, ['Kiwi', 'Schtroumpf']))
            self.dummy_process_obj.transition_steps_check(session)
            self.assertRaises(UserError,
                            self.dummy_process_obj.transition_master_step,
                            session)
            self.dummy_process_obj.transition_steps_next(session)
            self.assertRaises(UserError,
                              self.dummy_process_obj.transition_master_step,
                              session)
            session.dummy_step.name = 'Titi'
            self.assertTupleEqual(
                        self.dummy_step_obj.check_step(
                                    session,
                                    {},
                                    session.process_state.cur_step_desc
                                                      ),
                        (True, []))
            self.dummy_process_obj.transition_steps_next(session)
            self.dummy_process_obj.transition_master_step(session)
            self.assertEqual(session.process_state.cur_action,
                             'go_next')
            self.assertEqual(session.process_state.cur_step,
                             'dummy_step1')
            self.assertEqual(session.dummy_step1.name,
                             'Titi')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ProcessTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
