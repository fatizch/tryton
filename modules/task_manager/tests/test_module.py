import unittest
from datetime import datetime
import trytond.tests.test_tryton

from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'task_manager'

    @classmethod
    def get_models(cls):
        return {
            'User': 'res.user',
            'Team': 'res.team',
            'Process': 'process',
            'ProcessStepRelation': 'process-process.step',
            'ProcessLog': 'process.log',
            'Priority': 'res.team.priority',
            'ProcessTestModel': 'process.test.model',
            'IrModel': 'ir.model',
            }

    def test0010prioritytask_calculation(self):
        team, = self.Team.create([{
                    'name': 'team 1',
                    'code': 'T1',
                    }])
        user1, user2, user3 = self.User.create([{
                    'name': 'user 1',
                    'login': 'user1',
                    'active': True,
                    'teams': [('add', [team.id])],
                    }, {
                    'name': 'user 2',
                    'login': 'user2',
                    'active': True,
                    'teams': [('add', [team.id])],
                    }, {
                    'name': 'user 3',
                    'login': 'user3',
                    'active': True,
                    'teams': [('add', [team.id])],
                    }])
        process_model, = self.IrModel.search([
                ('model', '=', self.ProcessTestModel.__name__)])
        test1, test2, test3 = self.ProcessTestModel.create([{}, {}, {}])
        process, = self.Process.create([{
                    'technical_name': 'process',
                    'fancy_name': 'process',
                    'on_model': process_model.id,
                    }])
        step1, step2, step3 = self.ProcessStepRelation.create([{
                    'process': process.id,
                    }, {
                    'process': process.id,
                    }, {
                    'process': process.id,
                    }])
        log1, log2, log3, log4, log5 = self.ProcessLog.create([{
                    'user': user1.id,
                    'to_state': step1,
                    'start_time': datetime(2014, 1, 1),
                    'latest': True,
                    'locked': False,
                    'task': '%s,%s' % (self.ProcessTestModel.__name__,
                        test1.id)
                    }, {
                    'user': user1.id,
                    'to_state': step1,
                    'start_time': datetime(2013, 1, 1),
                    'latest': False,
                    'locked': False,
                    'task': '%s,%s' % (self.ProcessTestModel.__name__,
                        test1.id)
                    }, {
                    'user': user1.id,
                    'to_state': step2,
                    'start_time': datetime(2014, 1, 1),
                    'task': '%s,%s' % (self.ProcessTestModel.__name__,
                        test2.id)
                    }, {
                    'user': user1.id,
                    'to_state': step1,
                    'start_time': datetime(2014, 1, 2),
                    'task': '%s,%s' % (self.ProcessTestModel.__name__,
                        test3.id)
                    }, {
                    'user': user2.id,
                    'to_state': step1,
                    'start_time': datetime(2014, 1, 1),
                    'task': '%s,%s' % (self.ProcessTestModel.__name__,
                        test1.id)
                    }])
        priority1, priority2, priority3 = self.Priority.create([{
                    'process_step': step1.id,
                    'team': team.id,
                    'value': 1,
                    }, {
                    'process_step': step2.id,
                    'team': team.id,
                    'value': 2,
                    }, {
                    'process_step': step3.id,
                    'team': team.id,
                    'value': 3,
                    }])
        self.assertEqual(user1.search_next_priority_task(), log1)
        priority1.value = 4
        priority1.save()
        self.assertEqual(user1.search_next_priority_task(), log3)
        priority3.value = 1
        priority3.save()
        self.assertEqual(user1.search_next_priority_task(), log3)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
