# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import datetime
from dateutil.relativedelta import relativedelta

import trytond.tests.test_tryton
from trytond.modules.cog_utils import test_framework


class ModuleTestCase(test_framework.CoopTestCase):
    '''
    Test Coop module.
    '''
    module = 'account_dunning_cog'

    @classmethod
    def get_models(cls):
        return {
            'Procedure': 'account.dunning.procedure',
            'Level': 'account.dunning.level',
            'Line': 'account.move.line',
            'Dunning': 'account.dunning',
            }

    def test0010_level(self):
        procedure = self.Procedure(name='Procedure', code='procedure')
        procedure.save()
        level1 = self.Level()
        level1.days = 20
        level1.name = 'Level1'
        level1.days_from_previous_step = False
        level1.not_mandatory = True
        level1.procedure = procedure
        level1.save()
        level2 = self.Level()
        level2.days = 60
        level2.not_mandatory = False
        level2.days_from_previous_step = False
        level2.name = 'Level2'
        level2.procedure = procedure
        level2.save()
        level3 = self.Level()
        level3.days = 10
        level3.name = 'Level3'
        level3.not_mandatory = False
        level3.days_from_previous_step = True
        level3.procedure = procedure
        level3.save()
        procedure.levels = [level1, level2, level3]
        procedure.save()

        today = datetime.date.today()
        line = self.Line()
        line.dunnings = []
        line.maturity_date = datetime.date.today()

        self.assertFalse(level3.test(line, today + relativedelta(days=19)))
        self.assertFalse(level1.test(line, today + relativedelta(days=19)))
        self.assertTrue(level1.test(line, today + relativedelta(days=20)))
        self.assertFalse(level1.test(line, today + relativedelta(days=60)))

        self.assertFalse(level2.test(line, today + relativedelta(days=59)))
        self.assertTrue(level2.test(line, today + relativedelta(days=60)))

        dunning = self.Dunning()
        dunning.last_process_date = today + relativedelta(days=60)
        dunning.level = level2
        line.dunnings = (dunning,)

        self.assertFalse(level3.test(line, today + relativedelta(days=69)))
        self.assertTrue(level3.test(line, today + relativedelta(days=70)))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ModuleTestCase))
    return suite
